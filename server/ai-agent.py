import os
import json
import subprocess
import datetime
import sys
import re
import uvicorn
from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import logging
import uuid
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("WARNING: boto3 not available, storage features disabled")

try:
    import psycopg2
    from psycopg2 import sql
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False
    print("WARNING: psycopg2 not available, database features disabled")

# ------------------------------------------------------------
# Logging with trace_id support
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

class TraceLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        trace_id = self.extra.get("trace_id", "none")
        return f"[trace_id={trace_id}] {msg}", kwargs

def extract_trace_id(request: Request) -> str:
    """Extract trace_id from headers or generate new if missing."""
    trace_id = (
        request.headers.get("x-datadog-trace-id")
        or request.headers.get("x-trace-id")
        or str(uuid.uuid4())
    )
    return trace_id

# ------------------------------------------------------------
# FastAPI App
# ------------------------------------------------------------
app = FastAPI(title="Swagger → k6 Generator with TraceID")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Gemini LLM (LangChain)
# ------------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key="AIzaSyAjTPS6kxScAPhZB_RphkzHiBeXeFMvKUw",
    temperature=0.2
)

# ------------------------------------------------------------
# Install and Build k6 (xk6) - Only build if needed
# ------------------------------------------------------------
def install_xk6_and_build():
    try:
        # Check if k6 executable exists
        k6_path = os.path.expanduser("~/go/bin/k6")
        if os.path.exists(k6_path):
            print("✅ k6 already built, skipping installation.")
            return

        print("Installing xk6...")
        subprocess.run(["go", "install", "go.k6.io/xk6/cmd/xk6@latest"], check=True)
        go_bin = os.path.expanduser("~/go/bin")
        os.environ["PATH"] += os.pathsep + go_bin
        print("Building k6 with TimescaleDB output...")
        subprocess.run([
            "xk6", "build",
            "--with", "github.com/grafana/xk6-output-timescaledb"
        ], check=True)
        print("✅ xk6 build complete.")
    except subprocess.CalledProcessError as e:
        print("Error during installation or build:", e)
        sys.exit(1)

install_xk6_and_build()

# ------------------------------------------------------------
# Prompt Template
# ------------------------------------------------------------
script_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in writing k6 load testing scripts in JavaScript. Generate ONLY the k6 JavaScript code - no explanations, no instructions, no markdown - just the pure script."),
    ("user", """
Using the provided Swagger specification, generate a complete k6 script that satisfies the following:
- Use {vus} virtual users and run for {duration}.
- Include modular GET requests for each endpoint in the Swagger spec.
- Include tracing headers and unique trace IDs per request.
- Add a helper function `getTracingHeaders()` that returns headers and tags for datadog compatible tracing
- Each HTTP request must send trace_id in their header.
- Do not follow redirects.
- pure script, no comments.
- Use trends to record response durations per endpoint.
- Use environment variables: BASE_URL=__ENV.BASE_URL
- don't use trend, checks and thresholds untils they are defined with content.
IMPORTANT: Use the correct base URL from the Swagger spec - do NOT hardcode localhost:8080.
Extract the base URL from the 'servers' array in the Swagger spec and use that as default.

Swagger Spec:
{swagger}
    """),
    MessagesPlaceholder(variable_name="history")
])


# ------------------------------------------------------------
# Session Store
# ------------------------------------------------------------
store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

conversation_with_history = RunnableWithMessageHistory(
    script_prompt | llm,
    get_session_history,
    input_messages_key="user",
    history_messages_key="history"
)

# ------------------------------------------------------------
# Request Model
# ------------------------------------------------------------
class K6Request(BaseModel):
    swagger: dict
    vus: int = 1
    duration: str = "30s"
    max_retries: int = 3
    session_id: str = "default-session"
    appName: str = "digital-deployer-quality"
    branchName: str = "develop"
    client_id_ok: str = "k6-test-client-ok"
    client_id_random: str = "k6-test-client-random"
    ok_token: str = "Bearer 123"

# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------
def extract_js_code(llm_output: str) -> str:
    import re

    # Look for code blocks with javascript/js markers first
    patterns = [
        r"```javascript\s*(.*?)```",
        r"```js\s*(.*?)```",
        r"```\s*k6.*?```",  # Look for any k6-related code blocks
        r"```(?:javascript|js)\s*(.*?)\s*```"
    ]

    for pattern in patterns:
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if code and ("import" in code or "export default function" in code or "http." in code):
                return code

    # If no code blocks found, try to find content that looks like JavaScript
    lines = llm_output.split('\n')
    code_start = -1

    for i, line in enumerate(lines):
        if 'export default function' in line or 'import ' in line:
            code_start = i
            break

    if code_start >= 0:
        # Extract from start marker to end
        code_lines = lines[code_start:]
        return '\n'.join(code_lines).strip()

    # Last resort - return the original output but clean it up
    return llm_output.strip()

# ------------------------------------------------------------
# Generate Script
# ------------------------------------------------------------
def generate_k6_script(req: K6Request, feedback: str = None) -> str:
    variables = {
        "swagger": json.dumps(req.swagger, indent=2),
        "vus": req.vus,
        "duration": req.duration,
        "client_id_ok": req.client_id_ok,
        "client_id_random": req.client_id_random,
        "ok_token": req.ok_token or ""
    }
    variables["user"] = f"The last script failed with error:\n{feedback}" if feedback else ""

    response = conversation_with_history.invoke(
        variables,
        config={"configurable": {"session_id": req.session_id}}
    )

    return response.content

# ------------------------------------------------------------
# Database Tables Creation for Persistent Storage
# ------------------------------------------------------------
def create_persistent_tables():
    """Create tables for persistent run storage"""
    try:
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        # Table for run metadata
        cur.execute("""
        CREATE TABLE IF NOT EXISTS run_history (
            id VARCHAR(255) PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            status VARCHAR(50) NOT NULL,
            app_name VARCHAR(255),
            branch_name VARCHAR(255),
            session_id VARCHAR(255),
            script_s3_url TEXT,
            result_s3_url TEXT,
            attempts INTEGER,
            run_type VARCHAR(50) DEFAULT 'define'
        );
        """)

        # Table for run execution details
        cur.execute("""
        CREATE TABLE IF NOT EXISTS run_execution_details (
            id VARCHAR(255) PRIMARY KEY,
            run_id VARCHAR(255) NOT NULL,
            script_text TEXT,
            execution_summary TEXT,
            k6_command TEXT,
            raw_output_file VARCHAR(500),
            summary_file VARCHAR(500),
            stdout TEXT,
            stderr TEXT,
            exit_code INTEGER,
            threshold_warning BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Remove foreign key constraint since we may have results without runs sometimes
        # FOREIGN KEY (run_id) REFERENCES run_history(id)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Persistent tables created/verified")
    except Exception as e:
        print(f"ERROR: Failed to create persistent tables: {e}")

create_persistent_tables()

# ------------------------------------------------------------
# Run k6
# ------------------------------------------------------------
# MinIO client setup (conditionally)
if BOTO3_AVAILABLE:
    s3_client = boto3.client(
        's3',
        endpoint_url='http://192.168.1.150:9000',
        aws_access_key_id='minioadm',
        aws_secret_access_key='minioadm',
        region_name='us-east-1'
    )
else:
    s3_client = None

def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Execute a command and return the result"""
    env = os.environ.copy()
    env["PATH"] += os.pathsep + "/opt/homebrew/bin"
    return subprocess.run(cmd, env=env, capture_output=True, text=True)

# Single function with deduplication
def run_k6(script_file: str, app_name: str, branch_name: str, summary_folder: str = "k6_summaries"):
    try:
        os.makedirs(summary_folder, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        tag_value = f"{app_name}-{branch_name}-{timestamp}"
        summary_file = os.path.join(summary_folder, f"{tag_value}-summary.json")
        raw_output_file = os.path.join(summary_folder, f"{tag_value}raw.ndjson")

        env = os.environ.copy()
        env["PATH"] += os.pathsep + "/opt/homebrew/bin"

        cmd = [
            "/opt/homebrew/bin/k6", "run",
            script_file,
            f"--summary-export={summary_file}",
            "--summary-trend-stats=avg,min,max,med,p(50),p(75),p(90),p(95),p(99.9)",
            "--tag", f"testid={tag_value}",
            "--out", f"json={raw_output_file}",
            "-e", "BASE_URL=http://localhost:8081",
            "-e", "K6_BASE_URL=http://localhost:8081",
            "-e", "X_CLIENT_ID=test-client",
            "-e", "AUTH_TOKEN=test-token",
            # TODO: Uncomment when TimescaleDB credentials are fixed
            "-o", f"timescaledb=postgresql://k6:k6@192.168.1.150:5432/k6"
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            return f"k6 run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}", None, None

        if not os.path.exists(summary_file):
            return "k6 run completed but summary file missing.", None, None

        with open(summary_file, "r") as f:
            summary_json = json.load(f)

        return None, summary_json, raw_output_file

    except FileNotFoundError:
        return "k6 executable not found. Please install k6 and ensure it's in PATH.", None, None
    except subprocess.CalledProcessError as e:
        return f"STDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", None, None

class SaveTemplateRequest(BaseModel):
    name: str
    script: str
    request_payload: dict
    run_id: str = None

class SaveScriptOnlyRequest(BaseModel):
    name: str
    script: str
    request_payload: dict
    run_id: str = None

def save_to_minio(bucket_name: str, object_name: str, file_content: str):
    """Save script content to MinIO."""
    try:
        # Create bucket if it doesn't exist
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                raise

        s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=file_content)
        return f"s3://{bucket_name}/{object_name}"
    except ClientError as e:
        return f"Failed to save to MinIO: {e}"

def save_metadata_to_postgres(name: str, s3_url: str, created_by: str, run_id: str = None):
    """Save metadata to PostgreSQL."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        # Create table if not exists
        create_table_query = """
        CREATE TABLE IF NOT EXISTS performance_scripts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            s3_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(255) NOT NULL,
            run_id VARCHAR(255)
        );
        """
        cur.execute(create_table_query)

        # Insert metadata
        insert_query = """
        INSERT INTO performance_scripts (name, s3_url, created_by, run_id)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(insert_query, (name, s3_url, created_by, run_id))
        conn.commit()
        cur.close()
    except Exception as e:
        return f"Failed to save metadata to PostgreSQL: {e}"
    finally:
        if conn:
            conn.close()

@app.post("/smoke-perf-script")
async def save_perf_script(req: SaveTemplateRequest, request: Request):
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info(f"Saving performance script template: {req.name}")

    try:
        bucket_name = "performance-scripts"
        object_name = f"{req.name}-{trace_id}.js"

        s3_url = save_to_minio(bucket_name, object_name, req.script)
        if s3_url.startswith("Failed"):
            raise HTTPException(status_code=500, detail=s3_url)

        created_by = req.request_payload.get('created_by', 'unknown')
        save_error = save_metadata_to_postgres(req.name, s3_url, created_by, req.run_id)

        if save_error:
            logger.error(save_error)
            raise HTTPException(status_code=500, detail=save_error)

        saved_at = datetime.datetime.now().isoformat()
        return {
            "id": trace_id,
            "name": req.name,
            "savedAt": saved_at,
            "s3_url": s3_url
        }

    except Exception as e:
        logger.exception("Internal Server Error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-script-only")
async def save_script_only(req: SaveScriptOnlyRequest, request: Request):
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info(f"Saving script only: {req.name}")

    try:
        bucket_name = "performance-scripts"
        object_name = f"{req.name}-{trace_id}.js"

        s3_url = save_to_minio(bucket_name, object_name, req.script)
        if s3_url.startswith("Failed"):
            raise HTTPException(status_code=500, detail=s3_url)

        created_by = req.request_payload.get('created_by', 'unknown')
        save_error = save_metadata_to_postgres(req.name, s3_url, created_by, req.run_id)

        if save_error:
            logger.error(save_error)
            raise HTTPException(status_code=500, detail=save_error)

        saved_at = datetime.datetime.now().isoformat()
        return {
            "id": trace_id,
            "name": req.name,
            "savedAt": saved_at,
            "s3_url": s3_url
        }

    except Exception as e:
        logger.exception("Internal Server Error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{app_name}")
async def get_application_by_name(app_name: str, request: Request):
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info(f"Fetching application: {app_name}")

    try:
        # Mock data for the digital-deployer-quality app
        if app_name == "digital-deployer-quality":
            return {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": app_name,
                "swagger_url": "http://localhost:8081/swagger/swagger.json",
                "project_id": "660e8400-e29b-41d4-a716-446655440001",
                "description": "Digital Deployer Quality Application",
                "owner": "dev-team",
                "url": "https://digital-deployer-quality.example.com"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Application {app_name} not found")

    except Exception as e:
        logger.exception("Internal Server Error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate-k6/results/{run_id}")
async def get_run_results(run_id: str, request: Request):
    """Get detailed results for a specific run"""
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info(f"Getting run results for: {run_id}")

    # Query the persistent database for run results
    try:
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        # Get run metadata
        cur.execute("""
        SELECT id, created_at, status, app_name, branch_name, session_id, script_s3_url, result_s3_url, attempts
        FROM run_history WHERE id = %s
        """, (run_id,))

        run_row = cur.fetchone()
        if not run_row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Get execution details
        cur.execute("""
        SELECT script_text, execution_summary, k6_command, raw_output_file, summary_file,
               stdout, stderr, exit_code, threshold_warning
        FROM run_execution_details WHERE run_id = %s
        """, (run_id,))

        exec_row = cur.fetchone()

        # Build the run detail response
        run_detail = {
            "id": run_row[0],
            "created_at": run_row[1].isoformat() if hasattr(run_row[1], 'isoformat') else str(run_row[1]),
            "status": run_row[2],
            "app_name": run_row[3],
            "branch_name": run_row[4] or "develop",
            "session_id": run_row[5],
            "request": {},  # Could be stored separately if needed
            "script": {
                "text": "",
                "lines": []
            },
            "execution": {
                "summary": "",
                "stdout": "",
                "stdout_lines": [],
                "stderr": "",
                "stderr_lines": [],
                "raw_output_file": "",
                "summary_file": "",
                "attempts": run_row[8] or 0,
                "exit_code": 0,
                "threshold_warning": False,
                "command": ""
            },
            "conversation_log": [],
            "archive": None
        }

        # Get script content from MinIO if available
        if run_row[6]:  # script_s3_url
            script_content = get_minio_content(run_row[6])
            run_detail["script"]["text"] = script_content
            run_detail["script"]["lines"] = script_content.split('\n') if script_content else []

        # Get execution details from database/MinIO
        if exec_row:
            exec_summary = exec_row[1]  # execution_summary
            run_detail["execution"]["summary"] = exec_summary
            run_detail["execution"]["stdout"] = exec_summary if isinstance(exec_summary, str) else json.dumps(exec_summary, indent=2) if exec_summary else ""
            run_detail["execution"]["stdout_lines"] = exec_summary.split('\n') if isinstance(exec_summary, str) and exec_summary else []
            run_detail["execution"]["stderr"] = exec_row[6] or ""
            run_detail["execution"]["stderr_lines"] = (exec_row[6] or "").split('\n')
            run_detail["execution"]["raw_output_file"] = exec_row[3] or ""
            run_detail["execution"]["summary_file"] = exec_row[4] or ""
            run_detail["execution"]["exit_code"] = exec_row[7] or 0
            run_detail["execution"]["threshold_warning"] = exec_row[8] or False
            run_detail["execution"]["command"] = exec_row[2] or ""

        cur.close()
        conn.close()

        return run_detail

    except psycopg2.Error as e:
        logger.error(f"Database error getting run results: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error getting run results: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/script-templates")
async def get_script_templates(request: Request, limit: int = 50, offset: int = 0):
    """Get saved script templates from the performance_scripts table"""
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info("Getting saved script templates")

    try:
        # Connect to PostgreSQL and fetch saved scripts
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        # Query the performance_scripts table for saved templates
        query = """
        SELECT id, name, s3_url, created_at, created_by, run_id
        FROM performance_scripts
        WHERE s3_url IS NOT NULL AND s3_url != ''
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
        """
        cur.execute(query, (limit, offset))
        rows = cur.fetchall()

        templates = []
        for row in rows:
            template_id, name, s3_url, created_at, created_by, run_id = row

            # Try to fetch the script content from MinIO (simple GET request)
            script_content = ""
            try:
                # Extract bucket name and key from s3:// URL
                if s3_url.startswith('s3://'):
                    path_parts = s3_url[5:].split('/', 1)
                    if len(path_parts) == 2:
                        bucket, key = path_parts
                        # Try to read from MinIO using boto3
                        if s3_client:
                            try:
                                response = s3_client.get_object(Bucket=bucket, Key=key)
                                script_content = response['Body'].read().decode('utf-8')
                            except Exception as s3_error:
                                logger.warning(f"Could not fetch script from MinIO: {s3_error}")
                                # For demo, we'll return a placeholder script
                                script_content = "// Script saved: " + str(created_at) + "\n// Load this from MinIO in production\n"
                        else:
                            # For demo, we'll return a placeholder script
                            script_content = "// Script saved: " + str(created_at) + "\n// Load this from MinIO in production\n"
            except Exception as minio_error:
                logger.warning(f"Could not fetch script from MinIO: {minio_error}")
                # For demo, we'll return a placeholder script
                script_content = "// Script saved: " + str(created_at) + "\n// Load this from MinIO in production\n"

            templates.append({
                "id": str(template_id),
                "name": name,
                "script": script_content,
                "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
                "created_by": created_by,
                "run_id": run_id,
                "request_payload": {},  # Could be stored separately in production
                "s3_url": s3_url
            })

        cur.close()
        conn.close()

        return {"templates": templates, "total": len(templates)}

    except Exception as e:
        logger.exception("Failed to fetch script templates")
        # Return empty list if DB not available
        return {"templates": [], "error": str(e)}

@app.get("/smoke-tests")
async def get_smoke_tests(request: Request, limit: int = 50, offset: int = 0):
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info(f"Fetching smoke tests - limit={limit}, offset={offset}")

    # Remove cache check completely - go directly to persistent storage
    try:
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        logger.info("Querying run_history table...")
        # Query the persistent run_history table
        query = """
        SELECT id, created_at, status, app_name, attempts
        FROM run_history
        WHERE run_type = 'define'
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
        """
        cur.execute(query, (int(limit), int(offset)))
        rows = cur.fetchall()

        logger.info(f"Found {len(rows)} runs in database")

        smoke_tests = []
        for row in rows:
            smoke_test = {
                "id": row[0],
                "created_at": row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1]),
                "status": row[2],
                "app_name": row[3],
                "branch_name": "develop",  # Default for now
                "session_id": f"session-{row[0].split('-')[1] if '-' in row[0] else '0'}",
                "attempts": row[4]
            }
            smoke_tests.append(smoke_test)

        cur.close()
        conn.close()

        logger.info(f"Returning {len(smoke_tests)} smoke tests")
        return {"smoke_tests": smoke_tests}

    except Exception as e:
        logger.exception(f"Failed to fetch smoke tests from persistent storage: {e}")
        # Return empty list on error
        return {"smoke_tests": []}

def get_minio_content(s3_url: str) -> str:
    """Fetch content from MinIO S3 URL"""
    if not s3_client:
        return ""

    try:
        # Extract bucket and key from s3://bucket/key format
        if s3_url.startswith('s3://'):
            bucket_key = s3_url[5:]
            if '/' in bucket_key:
                bucket, key = bucket_key.split('/', 1)
                response = s3_client.get_object(Bucket=bucket, Key=key)
                return response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to fetch content from MinIO: {s3_url} - {e}")
    return ""

def save_run_to_persistent_storage(run_id: str, run_data: dict, script_content: str, execution_data: dict) -> None:
    """Save run data to persistent storage (PostgreSQL + MinIO)"""
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    try:
        conn = psycopg2.connect(
            dbname="myuser",
            user="myuser",
            password="mypassword",
            host="localhost",
            port="5555"
        )
        cur = conn.cursor()

        # Save run metadata to run_history table
        run_meta = run_data
        cur.execute("""
        INSERT INTO run_history (id, created_at, status, app_name, branch_name, session_id, attempts, run_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """, (
            run_meta["id"],
            run_meta["created_at"],
            run_meta["status"],
            run_meta.get("app_name"),
            run_meta.get("branch_name"),
            run_meta.get("session_id"),
            run_meta.get("execution", {}).get("attempts", 0),
            "define"
        ))

        # Save script to MinIO and get URL
        script_bucket = "performance-scripts"
        script_key = f"scripts/{run_id}-script.js"
        script_s3_url = ""
        if s3_client:
            try:
                s3_client.put_object(Bucket=script_bucket, Key=script_key, Body=script_content)
                script_s3_url = f"s3://{script_bucket}/{script_key}"

                # Update script_s3_url in run_history
                cur.execute("""
                UPDATE run_history SET script_s3_url = %s WHERE id = %s
                """, (script_s3_url, run_id))
            except Exception as e:
                logger.error(f"Failed to save script to MinIO: {e}")

        # Save execution data to MinIO and get URL
        result_bucket = "performance-results"
        result_key = f"results/{run_id}-result.json"
        result_s3_url = ""
        exec_data_json = json.dumps(execution_data)
        if s3_client:
            try:
                s3_client.put_object(Bucket=result_bucket, Key=result_key, Body=exec_data_json)
                result_s3_url = f"s3://{result_bucket}/{result_key}"

                # Update result_s3_url in run_history
                cur.execute("""
                UPDATE run_history SET result_s3_url = %s WHERE id = %s
                """, (result_s3_url, run_id))
            except Exception as e:
                logger.error(f"Failed to save execution result to MinIO: {e}")

        # Save execution details to run_execution_details table
        exec_detail = execution_data
        cur.execute("""
        INSERT INTO run_execution_details
        (id, run_id, script_text, execution_summary, k6_command, raw_output_file, summary_file, stdout, stderr, exit_code, threshold_warning)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """, (
            f"{run_id}-exec",
            run_id,
            script_content,
            exec_data_json,
            exec_detail.get("command"),
            exec_detail.get("raw_output_file"),
            exec_detail.get("summary_file"),
            exec_detail.get("stdout"),
            exec_detail.get("stderr"),
            exec_detail.get("exit_code", 0),
            exec_detail.get("threshold_warning", False)
        ))

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Saved run {run_id} to persistent storage")
    except Exception as e:
        logger.error(f"Failed to save run to persistent storage: {e}")

# ------------------------------------------------------------
# Main Endpoint
# ------------------------------------------------------------
@app.post("/generate-k6")
async def generate_k6(req: K6Request, request: Request):
    trace_id = extract_trace_id(request)
    logger = TraceLoggerAdapter(logging.getLogger(__name__), {"trace_id": trace_id})
    logger.info("Received /generate-k6 request")

    try:
        script_file = "test.js"
        last_error = None

        for attempt in range(req.max_retries):
            script_content = generate_k6_script(req, last_error)
            script_content = extract_js_code(script_content)

            if not script_content.strip() or "export default function" not in script_content:
                last_error = "Generated script invalid."
                continue

            with open(script_file, "w") as f:
                f.write(script_content)

            last_error, execution_summary, raw_output_file = run_k6(
                script_file, req.appName, req.branchName
            )

            if not last_error:
                logger.info("✅ k6 run completed successfully.")

                # Generate run ID
                run_id = f"run-{int(datetime.datetime.now().timestamp())}"

                # Prepare run metadata
                run_data = {
                    "id": run_id,
                    "created_at": datetime.datetime.now().isoformat(),
                    "status": "completed",
                    "app_name": req.appName,
                    "branch_name": req.branchName,
                    "session_id": req.session_id
                }

                # Prepare execution data
                execution_data = {
                    "summary": execution_summary,
                    "stdout": execution_summary if isinstance(execution_summary, str) else json.dumps(execution_summary, indent=2),
                    "stdout_lines": execution_summary.split('\n') if isinstance(execution_summary, str) else [json.dumps(execution_summary, indent=2)],
                    "stderr": None,
                    "stderr_lines": [],
                    "raw_output_file": raw_output_file,
                    "summary_file": None,
                    "attempts": attempt + 1,
                    "exit_code": 0,
                    "threshold_warning": False,
                    "command": " ".join([
                        "/opt/homebrew/bin/k6",
                        "run",
                        script_file,
                        f"--summary-export=k6_summaries/{req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-summary.json",
                        "--summary-trend-stats=avg,min,max,med,p(50),p(75),p(90),p(95),p(99.9)",
                        "--tag", f"testid={req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
                        "--out", f"json=k6_summaries/{req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}raw.ndjson",
                        "-e", "BASE_URL=http://localhost:8081",
                        "-e", "K6_BASE_URL=http://localhost:8081",
                        "-e", "X_CLIENT_ID=test-client",
                        "-e", "AUTH_TOKEN=test-token"
                    ]),
                }

                # Store the last request payload for UI display (save to execution_data)
                last_request_payload = {
                    "session_id": req.session_id,
                    "vus": req.vus,
                    "appName": req.appName,
                    "app_name": req.appName,
                    "config": {
                        "vus": req.vus,
                        "duration": req.duration,
                        "max_retries": req.max_retries,
                        "thresholds_requested": False,
                    },
                    "stage_order": ["setup", "default", "teardown"],
                    "stages": {
                        "setup": [],
                        "default": [],
                        "teardown": []
                    },
                    "request_sequence": [],
                    "checks": {
                        "available_types": ["Status Code", "Header", "JSON Field", "Body Text", "Response Time"],
                        "requested_types": [],
                        "has_checks": False,
                        "total": 0,
                    },
                    "thresholds": {
                        "requested": False,
                        "definitions": [],
                    },
                    "swagger": req.swagger,
                    "raw_swagger": None,
                    "stage_groups": {
                        "Setup": [],
                        "Performance": [],
                        "Teardown": []
                    },
                    "base_url": None,
                    "include_comments": False,
                    "checks_summary": {
                        "total_performance_checks": 0,
                        "has_performance_checks": False,
                    },
                    "metadata": {
                        "ui_selected_vus": req.vus,
                        "ui_selected_duration": req.duration,
                    }
                }

                # Add request payload to execution_data for UI display
                execution_data["request_payload"] = last_request_payload
                exec_data_json = json.dumps(execution_data)

                # Save to persistent storage (PostgreSQL + MinIO)
                save_run_to_persistent_storage(run_id, run_data, script_content, execution_data)

                return {
                    "trace_id": trace_id,
                    "run_id": run_id,
                    "script_file_content": script_content,
                    "execution_summary": execution_summary,
                    "raw_output_file": raw_output_file,
                    "attempts": attempt + 1
                }
        else:
            # k6 run failed, prepare execution data anyway for logging/debugging
            execution_data = {
                "summary": None,
                "stdout": last_error if last_error else "",
                "stdout_lines": (last_error if last_error else "").split('\n'),
                "stderr": "",
                "stderr_lines": [],
                "raw_output_file": "",
                "summary_file": None,
                "attempts": attempt + 1,
                "exit_code": 1,
                "threshold_warning": False,
                "command": " ".join([
                    "/opt/homebrew/bin/k6",
                    "run",
                    script_file,
                    f"--summary-export=k6_summaries/{req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-summary.json",
                    "--summary-trend-stats=avg,min,max,med,p(50),p(75),p(90),p(95),p(99.9)",
                    "--tag", f"testid={req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
                    "--out", f"json=k6_summaries/{req.appName}-{req.branchName}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}raw.ndjson",
                    "-e", "BASE_URL=http://localhost:8081",
                    "-e", "K6_BASE_URL=http://localhost:8081",
                    "-e", "X_CLIENT_ID=test-client",
                    "-e", "AUTH_TOKEN=test-token"
                ]),
            }

        logger.error("❌ Failed after retries.")
        return {
            "trace_id": trace_id,
            "error": "Failed after retries.",
            "last_error": last_error,
            "script_file_content": script_content
        }

    except Exception as e:
        logger.exception("Internal Server Error")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------
# Run Server
# ------------------------------------------------------------
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"

if __name__ == "__main__":
    uvicorn.run("ai-agent:app", host="0.0.0.0", port=9999, reload=True)
