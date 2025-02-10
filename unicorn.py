import io
import os
import socket
from urllib.parse import urlparse
from index import app  # Import the Flask app

def handle_request(client_socket, flask_app):
    request_data = b""
    # Read HTTP request until end of headers
    while True:
        chunk = client_socket.recv(4096)
        if not chunk:
            break
        request_data += chunk
        if b"\r\n\r\n" in request_data:
            break

    try:
        # Parse HTTP request line
        request_line, _ = request_data.split(b"\r\n\r\n", 1)
        request_line_parts = request_line.split(b" ")
        method = request_line_parts[0].decode()
        path = request_line_parts[1].decode()

        parsed_url = urlparse(path)
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': parsed_url.path,
            'QUERY_STRING': parsed_url.query,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': io.BytesIO(),  # For GET requests; adjust if needed
            'wsgi.errors': io.BytesIO(),
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

        def start_response(status, headers, exc_info=None):
            status_line = f"HTTP/1.1 {status}\r\n".encode()
            headers_lines = b"".join(f"{header}: {value}\r\n".encode() for header, value in headers)
            client_socket.sendall(status_line + headers_lines + b"\r\n")
            return client_socket.sendall

        response_body = flask_app(environ, start_response)
        for chunk in response_body:
            # Ensure chunk is bytes
            if isinstance(chunk, str):
                chunk = chunk.encode('utf-8')
            client_socket.sendall(chunk)

    except Exception as e:
        error_response = b"HTTP/1.1 500 Internal Server Error\r\n\r\nInternal Server Error"
        client_socket.sendall(error_response)

    finally:
        client_socket.close()

def create_unix_server(flask_app, socket_path="/tmp/myapp.sock"):
    # Remove any existing socket file
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_socket.bind(socket_path)
    os.chmod(socket_path, 0o777)  # Set permissions so Nginx can access it
    server_socket.listen(5)
    print(f"Listening on Unix socket: {socket_path}")

    try:
        while True:
            client_socket, _ = server_socket.accept()
            handle_request(client_socket, flask_app)
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        server_socket.close()
        if os.path.exists(socket_path):
            os.remove(socket_path)

if __name__ == "__main__":
    create_unix_server(app)
