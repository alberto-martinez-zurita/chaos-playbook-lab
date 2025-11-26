"""
Diagnostic script to find the problematic endpoint in Petstore OpenAPI spec.

This will:
1. Download the spec
2. Parse all endpoints
3. Find which one is #7
4. Show what's wrong with it
"""

import json
import requests

# Download spec
print("Downloading Petstore OpenAPI spec...")
response = requests.get("https://petstore3.swagger.io/api/v3/openapi.json")
spec = response.json()

print("\n" + "="*70)
print("ANALYZING ENDPOINTS")
print("="*70)

# Extract all operations
operations = []
for path, methods in spec['paths'].items():
    for method, operation in methods.items():
        if method in ['get', 'post', 'put', 'delete', 'patch']:
            operations.append({
                'path': path,
                'method': method.upper(),
                'operationId': operation.get('operationId', 'UNKNOWN'),
                'parameters': operation.get('parameters', []),
                'requestBody': operation.get('requestBody', {})
            })

print(f"\nTotal operations found: {len(operations)}")
print("\n" + "-"*70)

# Print all operations with index
for idx, op in enumerate(operations):
    print(f"\n[{idx}] {op['method']} {op['path']}")
    print(f"    Operation ID: {op['operationId']}")
    
    # Check parameters
    if op['parameters']:
        print(f"    Parameters: {len(op['parameters'])}")
        for param in op['parameters']:
            param_name = param.get('name', '<<EMPTY>>')
            print(f"      - {param_name}: {param.get('in', 'unknown')}")
            
            # Check for empty keys in schema properties
            if 'schema' in param and 'properties' in param['schema']:
                props = param['schema']['properties']
                if isinstance(props, dict):
                    for key, value in props.items():
                        if not key or key.strip() == '':
                            print(f"        ⚠️  EMPTY KEY FOUND in schema properties!")
    
    # Check requestBody
    if op['requestBody']:
        print(f"    RequestBody: present")
        content = op['requestBody'].get('content', {})
        for content_type, content_schema in content.items():
            if 'schema' in content_schema:
                schema = content_schema['schema']
                if '$ref' in schema:
                    print(f"      - {content_type}: $ref {schema['$ref']}")
                elif 'properties' in schema:
                    props = schema['properties']
                    if isinstance(props, dict):
                        print(f"      - {content_type}: {len(props)} properties")
                        for key, value in props.items():
                            if not key or key.strip() == '':
                                print(f"        ⚠️  EMPTY KEY FOUND in requestBody properties!")

print("\n" + "="*70)
print("CHECKING COMPONENTS/SCHEMAS")
print("="*70)

if 'components' in spec and 'schemas' in spec['components']:
    for schema_name, schema_def in spec['components']['schemas'].items():
        if 'properties' in schema_def:
            props = schema_def['properties']
            if isinstance(props, dict):
                for key, value in props.items():
                    if not key or key.strip() == '':
                        print(f"\n⚠️  EMPTY KEY FOUND in schema '{schema_name}'")
                        print(f"    Properties: {list(props.keys())}")

print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)
print("\nLook for operation [7] above - that's the problematic one!")
print("Check for '⚠️  EMPTY KEY FOUND' messages.")
