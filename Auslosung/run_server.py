import http.server
import socketserver
import json
import os

PORT = 8000

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                draw_id = data.get('drawId', 'data')
                
                # Sanitize draw_id to prevent path traversal
                draw_id = "".join(c for c in draw_id if c.isalnum() or c in ('_', '-'))
                filename = f"results_{draw_id}.json"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
