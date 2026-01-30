# /api-spec-generator - Generate OpenAPI Specifications from Code

Analyzes API code and generates OpenAPI 3.0 specification files.

## Usage

```
/api-spec-generator --skill-arg src/api/routes.py
/api-spec-generator --skill-arg server.js
./claude-loop.sh --skill api-spec-generator --skill-arg api/endpoints.ts
```

## What This Skill Does

Extracts API endpoints from source code and generates OpenAPI specs:
1. **Endpoint detection**: Finds route definitions (Express, Flask, FastAPI, etc.)
2. **Method extraction**: Identifies HTTP methods (GET, POST, PUT, DELETE)
3. **Parameter detection**: Extracts path, query, and body parameters
4. **Response schemas**: Infers response types from return statements
5. **OpenAPI generation**: Creates valid OpenAPI 3.0 YAML/JSON output

## Supported Frameworks

- Python: Flask, FastAPI, Django REST Framework
- JavaScript/TypeScript: Express, Koa, NestJS
- Go: Gin, Echo, Chi
- Ruby: Rails, Sinatra

## Example Output

```yaml
openapi: 3.0.0
info:
  title: Generated API Spec
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: Success
    post:
      summary: Create user
      requestBody:
        required: true
      responses:
        '201':
          description: Created
```

## Exit Codes

- `0` - Spec generated successfully
- `1` - Error generating spec
- `2` - No endpoints found

## Script Implementation

Implemented in Python with framework-specific parsers.
