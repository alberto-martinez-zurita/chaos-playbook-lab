"""
generate_unit_tests_from_swagger.py - Auto-genera unit tests desde OpenAPI/Swagger

USO:

poetry run python scripts/generate_unit_tests_from_swagger.py ^
  --swagger-url https://petstore3.swagger.io/api/v3/openapi.json ^
  --output data/unit_tests_petstore.json

Propósito:
- Para cada operación (operationId) generar al menos 1 test "happy-path"
- Inferir valores razonables para parámetros obligatorios (path, query, body simple)
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


# ---------------------------------------------------------------------------
# Descarga del Swagger / OpenAPI
# ---------------------------------------------------------------------------

def fetch_swagger_spec(swagger_url: str) -> Dict[str, Any]:
    """
    Descarga o lee el spec desde url http(s) o archivo local.
    """
    if swagger_url.startswith("http://") or swagger_url.startswith("https://"):
        print(f'📥 Downloading Swagger spec from: {swagger_url}')
        resp = requests.get(swagger_url, timeout=10)
        resp.raise_for_status()
        spec = resp.json()
    else:
        print(f'📄 Loading Swagger spec from file: {swagger_url}')
        with open(swagger_url, "r", encoding="utf-8") as f:
            spec = json.load(f)
    info = spec.get('info', {})
    print('✅ Loaded Swagger spec')
    print(f'   Title:   {info.get("title", "Unknown")}')
    print(f'   Version: {info.get("version", "Unknown")}')
    return spec

# ---------------------------------------------------------------------------
# Inferencia de ejemplos a partir de schemas OpenAPI
# ---------------------------------------------------------------------------

def infer_example_from_schema(schema: Dict[str, Any]) -> Any:
    """Devuelve un valor de ejemplo simple para un schema OpenAPI."""
    if not schema:
        return "example"

    if "example" in schema:
        return schema["example"]

    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]

    t = schema.get("type")
    fmt = schema.get("format")

    if t == "string":
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        if fmt == "date":
            return "2025-01-01"
        return "example"

    if t == "integer":
        return 1

    if t == "number":
        return 1.0

    if t == "boolean":
        return True

    if t == "array":
        item_schema = schema.get("items", {})
        return [infer_example_from_schema(item_schema)]

    if t == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        obj: Dict[str, Any] = {}
        for name, prop_schema in props.items():
            # Si no hay "required", metemos todos; si lo hay, solo los required
            if not required or name in required:
                obj[name] = infer_example_from_schema(prop_schema)
        return obj

    return "example"


def build_params_for_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construye un dict de params para una operación OpenAPI:
    - Incluye query/path/header params simples
    - Si hay requestBody application/json sencillo, lo aplana en params
    """
    params: Dict[str, Any] = {}

    # 1) parameters (query, path, header, cookie)
    for p in op.get("parameters", []):
        name = p.get("name")
        if not name:
            continue

        schema = p.get("schema", {})
        required = p.get("required", False)

        if required or schema.get("type") in ("string", "integer", "number", "boolean"):
            example = infer_example_from_schema(schema)
            params[name] = example

    # 2) requestBody (solo application/json)
    request_body = op.get("requestBody")
    if request_body:
        content = request_body.get("content", {})
        app_json = content.get("application/json")
        if app_json:
            schema = app_json.get("schema", {})
            body_example = infer_example_from_schema(schema)
            if isinstance(body_example, dict):
                for k, v in body_example.items():
                    params.setdefault(k, v)
            else:
                params.setdefault("body", body_example)

    return params


# ---------------------------------------------------------------------------
# Generación de unit tests
# ---------------------------------------------------------------------------

def generate_unit_tests(swagger_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Genera una estructura JSON de unit tests a partir del spec OpenAPI.

    Estrategia:
    - Para cada path+method con operationId:
        - Crear un test "happy_path"
        - Params: inferidos con build_params_for_operation()
    """
    tests: List[Dict[str, Any]] = []
    paths = swagger_spec.get("paths", {})

    counter = 1
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                continue

            operation_id = op.get("operationId")
            if not operation_id:
                continue

            params = build_params_for_operation(op)
            test_id = f"UT_{counter:04d}"
            test_name = f"{operation_id}_happy_path"

            test_case = {
                "test_id": test_id,
                "test_name": test_name,
                "operation": operation_id,
                "http_method": method.upper(),
                "api_path": path,
                "params": params,
                "expected_success": True,
                "timeout_seconds": 10
            }
            tests.append(test_case)
            counter += 1

    info = swagger_spec.get("info", {})
    suite = {
        "test_suite": f"{info.get('title', 'api')}_unit_tests",
        "description": "Auto-generated happy-path unit tests from OpenAPI spec",
        "generated_from": info.get("title", "Unknown API"),
        "api_version": info.get("version", "Unknown"),
        "total_tests": len(tests),
        "tests": tests,
    }

    print(f"\n✅ Generated {len(tests)} unit tests")
    return suite


def save_unit_tests(test_suite: Dict[str, Any], output_file: str) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_suite, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved unit tests to {output_file}")
    print(f"   Total tests: {test_suite.get('total_tests', 0)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate unit tests from Swagger/OpenAPI spec")
    parser.add_argument("--swagger-url", required=True, help="URL to swagger.json / openapi.json")
    parser.add_argument("--output", required=True, help="Output JSON file for unit tests")
    args = parser.parse_args()

    spec = fetch_swagger_spec(args.swagger_url)
    suite = generate_unit_tests(spec)
    save_unit_tests(suite, args.output)


if __name__ == "__main__":
    main()
