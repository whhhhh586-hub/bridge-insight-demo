#!/usr/bin/env python3
"""Local site + optional model adapter; no third-party dependencies."""
import os, json, math, base64, urllib.request, urllib.error, urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
MODEL_URL = os.environ.get('QIAOAN_MODEL_URL', '').strip()
TOKEN = os.environ.get('QIAOAN_MODEL_TOKEN', '')
MODEL_NAME = os.environ.get('QIAOAN_MODEL_NAME', '自定义检测服务')[:100]
MAX_BODY = 8 * 1024 * 1024

def validate_regions(data):
    rows = data.get('regions')
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError('模型 regions 必须为数组，最多 200 个区域')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('区域必须是对象')
        box = row.get('box')
        if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box) or box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError('模型坐标必须为归一化 [x0,y0,x1,y1] 且范围有效')
        if not isinstance(row.get('label'), str) or not row['label'].strip():
            raise ValueError('模型须提供非空 label')
        r = {'box': box, 'label': row['label'][:60]}
        if 'score' in row:
            if type(row['score']) not in (int, float) or not math.isfinite(row['score']) or not 0 <= row['score'] <= 1:
                raise ValueError('模型 score 必须在 0 到 1 之间')
            r['score'] = row['score']
        result.append(r)
    return result

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def respond(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if self.path == '/api/health':
            return self.respond(200, {'configured': bool(MODEL_URL), 'host': urllib.parse.urlparse(MODEL_URL).hostname or '', 'model': MODEL_NAME})
        if self.path.startswith('/api/'):
            return self.respond(404, {'error': '接口不存在'})
        return super().do_GET()
    def do_POST(self):
        if self.path != '/api/detect':
            return self.respond(404, {'error': '接口不存在'})
        # Local adapter is same-origin only; do not make it an anonymous relay.
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            return self.respond(403, {'error': '仅允许本机访问'})
        if origin and origin not in ('http://' + host, 'https://' + host):
            return self.respond(403, {'error': '拒绝跨站调用'})
        if not MODEL_URL:
            return self.respond(503, {'error': '尚未配置 QIAOAN_MODEL_URL'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                return self.respond(413, {'error': '请求超过 8 MB 或为空'})
            data = json.loads(self.rfile.read(length))
            image = data.get('image', '')
            if not isinstance(image, str) or not image.startswith(('data:image/jpeg;base64,', 'data:image/png;base64,', 'data:image/webp;base64,')):
                raise ValueError('图片格式无效')
            base64.b64decode(image.split(',', 1)[1], validate=True)
            headers = {'Content-Type': 'application/json'}
            if TOKEN:
                headers['Authorization'] = 'Bearer ' + TOKEN
            request = urllib.request.Request(MODEL_URL, data=json.dumps({'image': image}).encode(), headers=headers, method='POST')
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ValueError('模型响应过大')
                model_data = json.loads(raw)
            return self.respond(200, {'model': MODEL_NAME, 'regions': validate_regions(model_data)})
        except urllib.error.HTTPError as e:
            return self.respond(502, {'error': '模型服务 HTTP ' + str(e.code) + '；请检查模型配置'})
        except (urllib.error.URLError, TimeoutError):
            return self.respond(504, {'error': '模型服务无法连接或超时'})
        except (ValueError, TypeError, AttributeError, KeyError):
            return self.respond(422, {'error': '图片请求或模型响应不符合接口协议'})
        except Exception:
            return self.respond(500, {'error': '模型调用失败，请检查服务端配置'})

if __name__ == '__main__':
    if MODEL_URL and urllib.parse.urlparse(MODEL_URL).scheme not in ('http', 'https'):
        raise SystemExit('QIAOAN_MODEL_URL 必须为 HTTP(S) 地址')
    port = int(os.environ.get('QIAOAN_PORT', '8080'))
    print(f'桥安探视已启动：http://127.0.0.1:{port}', flush=True)
    print('专业模型：' + ('已配置' if MODEL_URL else '未配置，本地图像初筛可用'), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
