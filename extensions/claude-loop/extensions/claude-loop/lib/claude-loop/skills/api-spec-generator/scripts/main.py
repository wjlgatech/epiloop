#!/usr/bin/env python3
"""
api-spec-generator skill - Generate OpenAPI specs from code

Extracts API endpoints and generates OpenAPI 3.0 specifications.
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Any

class APISpecGenerator:
    """Generates OpenAPI specifications from source code."""

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.endpoints: List[Dict[str, Any]] = []

    def extract_endpoints_python(self, content: str) -> None:
        """Extract Flask/FastAPI endpoints."""
        # Flask: @app.route('/path', methods=['GET', 'POST'])
        flask_pattern = r'@app\.route\([\'"]([^\'"]+)[\'"]\s*,?\s*methods=\[([^\]]+)\]'
        # FastAPI: @app.get('/path')
        fastapi_pattern = r'@app\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]\)'

        for match in re.finditer(flask_pattern, content):
            path = match.group(1)
            methods = match.group(2).replace("'", "").replace('"', "").split(',')
            for method in methods:
                self.endpoints.append({'path': path, 'method': method.strip().lower()})

        for match in re.finditer(fastapi_pattern, content):
            method = match.group(1)
            path = match.group(2)
            self.endpoints.append({'path': path, 'method': method.lower()})

    def extract_endpoints_javascript(self, content: str) -> None:
        """Extract Express.js endpoints."""
        # Express: app.get('/path', ...)
        pattern = r'app\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]\s*,'
        for match in re.finditer(pattern, content):
            method = match.group(1)
            path = match.group(2)
            self.endpoints.append({'path': path, 'method': method.lower()})

    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI 3.0 specification."""
        spec: Dict[str, Any] = {
            'openapi': '3.0.0',
            'info': {
                'title': f'API Spec for {self.source_path.name}',
                'version': '1.0.0'
            },
            'paths': {}
        }

        for endpoint in self.endpoints:
            path = endpoint['path']
            method = endpoint['method']

            if path not in spec['paths']:
                spec['paths'][path] = {}

            spec['paths'][path][method] = {
                'summary': f'{method.upper()} {path}',
                'responses': {
                    '200': {'description': 'Success'}
                }
            }

        return spec

    def generate(self) -> bool:
        """Main generation workflow."""
        if not self.source_path.exists():
            print(f"Error: Source file not found: {self.source_path}")
            return False

        try:
            with open(self.source_path, 'r') as f:
                content = f.read()

            # Detect language and extract endpoints
            if self.source_path.suffix == '.py':
                self.extract_endpoints_python(content)
            elif self.source_path.suffix in ['.js', '.ts']:
                self.extract_endpoints_javascript(content)
            else:
                print(f"Error: Unsupported file type: {self.source_path.suffix}")
                return False

            if not self.endpoints:
                print("No API endpoints found in source file")
                return False

            print(f"API Spec Generator v1.0")
            print("=" * 50)
            print(f"Source: {self.source_path}")
            print(f"Found {len(self.endpoints)} endpoint(s)")
            print()

            spec = self.generate_openapi_spec()

            # Output as YAML-style for readability
            print("openapi: 3.0.0")
            print("info:")
            print(f"  title: {spec['info']['title']}")
            print(f"  version: {spec['info']['version']}")
            print("paths:")

            for path, methods in spec['paths'].items():
                print(f"  {path}:")
                for method, details in methods.items():
                    print(f"    {method}:")
                    print(f"      summary: {details['summary']}")
                    print(f"      responses:")
                    for code, resp in details['responses'].items():
                        print(f"        '{code}':")
                        print(f"          description: {resp['description']}")

            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage: api-spec-generator <source_file>")
        sys.exit(2)

    generator = APISpecGenerator(sys.argv[1])
    success = generator.generate()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
