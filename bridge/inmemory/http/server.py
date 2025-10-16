from ....http import Request
from asyncio import sleep, start_server

from ....util import logger


class CronScheduler:
    """Handles periodic execution of cron tasks"""
    
    def __init__(self, app, container_builder, interval=30):
        self.app = app
        self.container_builder = container_builder
        self.interval = interval
    
    async def run(self):
        """Run the cron task every interval seconds"""
        logger().info(f"Starting cron task scheduler (every {self.interval} seconds)")
        while True:
            try:
                logger().info("Running cron task...")
                await self.app.kernel.cron(self.container_builder)
                logger().info("Cron task completed")
            except Exception as e:
                logger().error(f"Error in cron task: {e}")
            await sleep(self.interval)


class HttpServer:
    """HTTP server that handles incoming requests"""
    
    def __init__(self, app, container_builder, host='0.0.0.0', port=8000):
        self.app = app
        self.container_builder = container_builder
        self.host = host
        self.port = port
    
    def parse_http_request(self, data):
        """Parse HTTP request from raw bytes"""
        try:
            lines = data.decode('utf-8').split('\r\n')
            request_line = lines[0].split(' ')
            method = request_line[0]
            path = request_line[1] if len(request_line) > 1 else '/'

            headers = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()

            body = '\r\n'.join(lines[body_start:]) if body_start < len(lines) else ''

            return method, path, headers, body
        except Exception as e:
            logger().error(f"Error parsing HTTP request: {e}")
            return 'GET', '/', {}, ''
    
    async def handle_connection(self, reader, writer):
        """Handle individual HTTP connections"""
        try:
            data = await reader.read(8192)
            if not data:
                writer.close()
                await writer.wait_closed()
                return

            method, path, headers, body = self.parse_http_request(data)

            # Log incoming request
            logger().info(f"Incoming HTTP request: {method} {path}")

            # Get host header
            host = headers.get('Host', f'{self.host}:{self.port}')

            # Convert to microapi Request
            url = f"http://{host}{path}"
            request = Request(
                url=url,
                method=method,
                body=body,
                headers=headers
            )

            # Handle request through the kernel
            response = await self.app.kernel.handle(request, self.container_builder)

            # Build HTTP response
            response_body = await response.body()
            response_headers = '\r\n'.join([f"{k}: {v}" for k, v in response.headers.as_dict().items()])

            http_response = (
                f"HTTP/1.1 {response.status_code} OK\r\n"
                f"{response_headers}\r\n"
                f"Content-Length: {len(response_body.encode('utf-8'))}\r\n"
                f"\r\n"
                f"{response_body}"
            )

            writer.write(http_response.encode('utf-8'))
            await writer.drain()

        except Exception as e:
            logger().error(f"Error handling connection: {e}")
            error_response = (
                "HTTP/1.1 500 Internal Server Error\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 21\r\n"
                "\r\n"
                "Internal Server Error"
            )
            writer.write(error_response.encode('utf-8'))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def run(self):
        """Start the HTTP server"""
        logger().info(f"Starting HTTP server on http://{self.host}:{self.port}")
        server = await start_server(self.handle_connection, self.host, self.port)

        async with server:
            await server.serve_forever()
