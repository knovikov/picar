"""Простой веб-сервер для фото и статуса."""

from __future__ import annotations

import html
import logging
import os
import threading
import asyncio
from pathlib import Path
from typing import Callable, Optional

from kidbot.core.bluetooth_setup import connect_bluetooth_device, disconnect_bluetooth_device, scan_bluetooth_devices
from kidbot.core.config import DEFAULT_CONFIG
from kidbot.core.debug_state import DebugStateStore
from kidbot.core.openai_health import check_openai_api_key
from kidbot.core.secrets import openai_key_status, save_openai_api_key
from kidbot.core.status import SystemStatus
from kidbot.core.updater import UpdateManager
from kidbot.core.wifi_setup import AccessPointConfig, connect_to_wifi, scan_wifi_networks, start_access_point

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
logger = logging.getLogger("kidbot.web")


def list_photo_files(photo_dir: Path) -> list[Path]:
    return sorted(
        (path for path in Path(photo_dir).iterdir() if path.suffix.lower() in PHOTO_EXTENSIONS),
        key=lambda path: path.name,
    )


def delete_photo_file(photo_dir: Path, filename: str) -> bool:
    path = _safe_photo_path(photo_dir, filename)
    if path.suffix.lower() not in PHOTO_EXTENSIONS:
        raise ValueError("not a photo")
    if not path.exists():
        return False
    path.unlink()
    return True


def build_status_payload(status: SystemStatus) -> dict[str, object]:
    return {
        "robot_name": status.robot_name,
        "version": status.version,
        "wifi_connected": status.wifi_connected,
        "internet_connected": status.internet_connected,
        "ip_address": status.ip_address,
        "controller_connected": status.controller_connected,
        "latest_error": status.latest_error,
        "uptime_seconds": round(status.uptime_seconds, 1),
    }


def create_app(
    photo_dir: Path,
    status_provider: Callable[[], SystemStatus],
    env_path: Optional[Path] = None,
    access_point_config: Optional[AccessPointConfig] = None,
    openai_model: Optional[str] = None,
    repo_dir: Optional[Path] = None,
    update_manager: Optional[UpdateManager] = None,
    debug_store: Optional[DebugStateStore] = None,
):
    try:
        from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse, HTMLResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for the web server. Run pip install -r requirements.txt") from exc
    globals()["WebSocket"] = WebSocket
    globals()["WebSocketDisconnect"] = WebSocketDisconnect

    app = FastAPI(title="KidBot")
    env_path = env_path or Path(".env")
    access_point_config = access_point_config or AccessPointConfig()
    openai_model = openai_model or DEFAULT_CONFIG["openai"]["chat_model"]
    repo_dir = Path(repo_dir or Path.cwd())
    update_manager = update_manager or UpdateManager(repo_dir)
    debug_store = debug_store or DebugStateStore()

    @app.get("/", response_class=HTMLResponse)
    def index():
        status = build_status_payload(status_provider())
        photos = list_photo_files(photo_dir)[-12:]
        return _render_index(status, photos, openai_key_status(env_path), access_point_config)

    @app.get("/photos", response_class=HTMLResponse)
    def photos_page():
        status = build_status_payload(status_provider())
        photos = list_photo_files(photo_dir)
        return _render_index(status, photos, openai_key_status(env_path), access_point_config)

    @app.get("/debug", response_class=HTMLResponse)
    def debug_page():
        return _render_debug_page()

    @app.get("/photos/{filename}")
    def get_photo(filename: str):
        try:
            path = _safe_photo_path(photo_dir, filename)
        except ValueError:
            raise HTTPException(status_code=400, detail="Bad photo name") from None
        if not path.exists():
            raise HTTPException(status_code=404, detail="Photo not found")
        return FileResponse(path, media_type="image/jpeg", filename=path.name)

    @app.get("/api/status")
    def api_status():
        return build_status_payload(status_provider())

    @app.get("/api/photos")
    def api_photos():
        return [_photo_payload(path) for path in list_photo_files(photo_dir)]

    @app.delete("/api/photos/{filename}")
    def api_delete_photo(filename: str):
        try:
            deleted = delete_photo_file(photo_dir, filename)
        except ValueError:
            raise HTTPException(status_code=400, detail="Bad photo name") from None
        if not deleted:
            raise HTTPException(status_code=404, detail="Photo not found")
        return {"ok": True, "message": "Фото удалено."}

    @app.get("/api/wifi/scan")
    def api_wifi_scan():
        return [network.__dict__ for network in scan_wifi_networks()]

    @app.post("/api/wifi/connect")
    async def api_wifi_connect(request: Request):
        data = await request.json()
        result = connect_to_wifi(str(data.get("ssid", "")), str(data.get("password", "")))
        return result.__dict__

    @app.post("/api/setup/access-point")
    def api_start_access_point():
        result = start_access_point(access_point_config)
        return result.__dict__

    @app.get("/api/bluetooth/scan")
    def api_bluetooth_scan():
        return [device.__dict__ for device in scan_bluetooth_devices()]

    @app.post("/api/bluetooth/connect")
    async def api_bluetooth_connect(request: Request):
        data = await request.json()
        result = connect_bluetooth_device(str(data.get("address", "")))
        return result.__dict__

    @app.post("/api/bluetooth/disconnect")
    async def api_bluetooth_disconnect(request: Request):
        data = await request.json()
        result = disconnect_bluetooth_device(str(data.get("address", "")))
        return result.__dict__

    @app.get("/api/openai-key")
    def api_openai_key_status():
        return openai_key_status(env_path)

    @app.post("/api/openai-key")
    async def api_save_openai_key(request: Request):
        data = await request.json()
        api_key = str(data.get("api_key", "")).strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is empty")
        save_openai_api_key(env_path, api_key)
        return {"ok": True, "message": "OpenAI API key сохранен.", **openai_key_status(env_path)}

    @app.post("/api/openai-key/check")
    def api_check_openai_key():
        key = openai_key_status(env_path)
        from kidbot.core.secrets import load_env_file

        api_key = os.environ.get("OPENAI_API_KEY") or load_env_file(env_path).get("OPENAI_API_KEY", "")
        result = check_openai_api_key(api_key, model=str(openai_model))
        return {**result.__dict__, "masked": key["masked"]}

    @app.get("/api/update/status")
    def api_update_status():
        return update_manager.status_payload()

    @app.post("/api/update/check")
    def api_update_check():
        return update_manager.check()

    @app.post("/api/update/apply")
    def api_update_apply():
        return update_manager.start_update()

    @app.post("/api/update/rollback")
    def api_update_rollback():
        return update_manager.start_rollback()

    @app.websocket("/ws/debug")
    async def websocket_debug(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                status = build_status_payload(status_provider())
                await websocket.send_json(debug_store.snapshot(status=status))
                await asyncio.sleep(0.05)
        except WebSocketDisconnect:
            return

    return app


def run_web_server(
    photo_dir: Path,
    status_provider: Callable[[], SystemStatus],
    host: str,
    port: int,
    env_path: Optional[Path] = None,
    access_point_config: Optional[AccessPointConfig] = None,
    openai_model: Optional[str] = None,
    repo_dir: Optional[Path] = None,
    update_manager: Optional[UpdateManager] = None,
    debug_store: Optional[DebugStateStore] = None,
) -> threading.Thread:
    import uvicorn

    app = create_app(
        photo_dir,
        status_provider,
        env_path=env_path,
        access_point_config=access_point_config,
        openai_model=openai_model,
        repo_dir=repo_dir,
        update_manager=update_manager,
        debug_store=debug_store,
    )
    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None

    def serve() -> None:
        try:
            server.run()
        except Exception:
            logger.exception("web server thread crashed")

    thread = threading.Thread(
        target=serve,
        daemon=True,
    )
    thread.start()
    return thread


def _safe_photo_path(photo_dir: Path, filename: str) -> Path:
    if "/" in filename or "\\" in filename:
        raise ValueError("nested paths are not allowed")
    path = Path(photo_dir) / filename
    if path.resolve().parent != Path(photo_dir).resolve():
        raise ValueError("photo must stay inside photo dir")
    return path


def _photo_payload(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "url": f"/photos/{path.name}",
        "download_url": f"/photos/{path.name}",
        "size_bytes": path.stat().st_size,
    }


def _render_index(
    status: dict[str, object],
    photos: list[Path],
    key_status: dict[str, str],
    access_point_config: AccessPointConfig,
) -> str:
    photo_cards = "\n".join(_render_photo_card(path) for path in photos)
    if not photo_cards:
        photo_cards = '<div class="empty">Фотографий пока нет. Нажми A на пульте, и тут появится первая добыча.</div>'

    return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KidBot Control</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dde7;
      --paper: #fbfcff;
      --mint: #1f9d76;
      --sun: #f4b740;
      --coral: #ef6f5e;
      --sky: #2f80ed;
      --panel: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(180deg, #fff8e7 0, #edf7ff 42%, #f8fbff 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .shell {{ max-width: 1120px; margin: 0 auto; padding: 20px; }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: end;
      padding: 16px 0 18px;
      border-bottom: 2px solid rgba(23, 32, 42, 0.08);
    }}
    h1 {{ margin: 0; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 22px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    .hero-note {{ max-width: 660px; margin-top: 6px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.75);
      font-weight: 700;
      white-space: nowrap;
    }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; background: var(--coral); }}
    .dot.good {{ background: var(--mint); }}
    .grid {{ display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 18px; margin-top: 18px; }}
    section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.86);
      padding: 16px;
      box-shadow: 0 10px 24px rgba(28, 39, 54, 0.08);
    }}
    .status-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .stat {{ border-left: 4px solid var(--sky); background: #f7fbff; padding: 10px; border-radius: 6px; }}
    .stat strong {{ display: block; font-size: 13px; color: var(--muted); margin-bottom: 3px; }}
    .photos {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }}
    .photo-card {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--panel); }}
    .photo-card img {{ width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; background: #e8edf5; font-size: 0; color: transparent; }}
    .photo-body {{ padding: 10px; }}
    .photo-name {{ font-weight: 700; font-size: 13px; word-break: break-word; min-height: 34px; }}
    .row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .photo-actions {{ margin-top: 10px; }}
    button, .button {{
      appearance: none;
      border: 0;
      border-radius: 8px;
      background: var(--ink);
      color: white;
      min-height: 38px;
      padding: 8px 12px;
      font-weight: 800;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }}
    button.secondary, .button.secondary {{ background: var(--sky); }}
    button.sun {{ background: var(--sun); color: #2b2105; }}
    button.danger {{ background: var(--coral); }}
    button:disabled {{ opacity: .55; cursor: not-allowed; }}
    label {{ display: block; font-weight: 800; margin: 10px 0 6px; }}
    input, select {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 16px;
      background: white;
    }}
    .stack {{ display: grid; gap: 14px; }}
    .empty {{ border: 1px dashed var(--line); border-radius: 8px; padding: 18px; color: var(--muted); background: #fff; }}
    .message {{ min-height: 24px; color: var(--muted); font-weight: 700; }}
    .small {{ font-size: 13px; }}
    .limit-box {{
      margin-top: 10px;
      display: grid;
      gap: 6px;
      padding: 10px;
      border-radius: 8px;
      background: #f7fbff;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }}
    .limit-box strong {{ color: var(--ink); }}
    .top-actions {{ display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }}
    .debug-link {{
      min-height: 34px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.75);
      color: var(--ink);
      font-weight: 800;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }}
    @media (max-width: 820px) {{
      .shell {{ padding: 14px; }}
      header {{ grid-template-columns: 1fr; align-items: start; }}
      h1 {{ font-size: 30px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .status-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>Picar</h1>
        <p class="hero-note">Фото, Wi-Fi, пульт и облачный мозг робота в одном месте. Большие кнопки, короткие слова, никакой паники.</p>
      </div>
      <div class="top-actions">
        <a class="debug-link" href="/debug">Debug</a>
        <div class="badge"><span class="dot {'good' if status["internet_connected"] else ''}"></span>{'Интернет есть' if status["internet_connected"] else 'Setup режим'}</div>
      </div>
    </header>

    <div class="grid">
      <div class="stack">
        <section>
          <h2>Фото</h2>
          <div class="photos" id="photos">{photo_cards}</div>
        </section>

        <section>
          <h2>Статус</h2>
          <div class="status-grid">
            <div class="stat"><strong>Адрес</strong>{html.escape(str(status["ip_address"]))}:8080</div>
            <div class="stat"><strong>Версия</strong>{html.escape(str(status["version"]))}</div>
            <div class="stat"><strong>Пульт</strong>{'подключен' if status["controller_connected"] else 'не найден'}</div>
            <div class="stat"><strong>OpenAI</strong>{html.escape(key_status["masked"])}</div>
          </div>
        </section>

        <section>
          <h2>Обновления</h2>
          <p class="small">Робот не скачивает код сам при включении. Сначала проверь обновление, потом нажми большую кнопку.</p>
          <div class="status-grid" style="margin-top: 10px">
            <div class="stat"><strong>Текущий</strong><span id="updateCurrent">?</span></div>
            <div class="stat"><strong>GitHub</strong><span id="updateRemote">?</span></div>
            <div class="stat"><strong>Стабильный</strong><span id="updateStable">не сохранен</span></div>
            <div class="stat"><strong>Задача</strong><span id="updateJob">idle</span></div>
          </div>
          <div class="row" style="margin-top: 12px">
            <button class="secondary" id="checkUpdateButton" type="button">Проверить</button>
            <button class="sun" id="applyUpdateButton" type="button">Обновить</button>
            <button class="danger" id="rollbackButton" type="button">Откатиться</button>
          </div>
          <p class="message" id="updateMessage">Готово. Обновления запускаются только отсюда.</p>
          <p class="small">Аварийный откат на пульте: зажать Select и Start примерно на 2 секунды.</p>
        </section>
      </div>

      <div class="stack">
        <section>
          <h2>Wi-Fi</h2>
          <p class="small">Если робот создал сеть {html.escape(access_point_config.ssid)}, подключись к ней и выбери домашний Wi-Fi тут.</p>
          <button class="secondary" id="scanButton" type="button">Сканировать сети</button>
          <label for="ssid">Сеть</label>
          <select id="ssid"><option value="">Сначала сканирование</option></select>
          <label for="wifiPassword">Пароль Wi-Fi</label>
          <input id="wifiPassword" type="password" autocomplete="current-password" placeholder="пароль от сети">
          <div class="row" style="margin-top: 12px">
            <button class="sun" id="connectButton" type="button">Подключить</button>
            <button class="secondary" id="apButton" type="button">Включить setup-сеть</button>
          </div>
          <p class="message" id="wifiMessage"></p>
        </section>

        <section>
          <h2>Пульт</h2>
          <p class="small">Включи pairing mode на Bluetooth-пульте, потом нажми поиск. Для 8BitDo обычно нужен режим Bluetooth.</p>
          <button class="secondary" id="bluetoothScanButton" type="button">Найти Bluetooth</button>
          <label for="bluetoothDevice">Устройство</label>
          <select id="bluetoothDevice"><option value="">Сначала поиск</option></select>
          <div class="row" style="margin-top: 12px">
            <button class="sun" id="bluetoothConnectButton" type="button">Подключить пульт</button>
            <button class="secondary" id="bluetoothDisconnectButton" type="button">Отключить</button>
          </div>
          <p class="message" id="bluetoothMessage"></p>
        </section>

        <section>
          <h2>OpenAI</h2>
          <p class="small">Ключ сохраняется только на роботе в локальном .env файле.</p>
          <label for="apiKey">API key</label>
          <input id="apiKey" type="password" autocomplete="off" placeholder="sk-...">
          <div class="row" style="margin-top: 12px">
            <button id="saveKeyButton" type="button">Сохранить ключ</button>
            <button class="secondary" id="checkKeyButton" type="button">Проверить ключ</button>
          </div>
          <p class="message" id="keyMessage">Сейчас: {html.escape(key_status["masked"])}</p>
          <div class="limit-box" id="limitBox">
            <div><strong>Лимиты:</strong> нажми “Проверить ключ”.</div>
            <div class="small">Покажу remaining requests/tokens из OpenAI headers. Баланс денег обычным robot key не видно.</div>
          </div>
        </section>
      </div>
    </div>
  </main>

  <script>
    async function jsonFetch(url, options = {{}}) {{
      const response = await fetch(url, {{
        headers: {{ 'Content-Type': 'application/json' }},
        ...options
      }});
      if (!response.ok) {{
        let detail = 'Ошибка';
        try {{ detail = (await response.json()).detail || detail; }} catch (error) {{}}
        throw new Error(detail);
      }}
      return response.json();
    }}

    document.querySelectorAll('[data-delete-photo]').forEach((button) => {{
      button.addEventListener('click', async () => {{
        const name = button.dataset.deletePhoto;
        if (!confirm('Удалить фото ' + name + '?')) return;
        button.disabled = true;
        try {{
          await jsonFetch('/api/photos/' + encodeURIComponent(name), {{ method: 'DELETE' }});
          button.closest('.photo-card').remove();
        }} catch (error) {{
          alert(error.message);
          button.disabled = false;
        }}
      }});
    }});

    document.getElementById('scanButton').addEventListener('click', async () => {{
      const message = document.getElementById('wifiMessage');
      const select = document.getElementById('ssid');
      message.textContent = 'Ищу сети...';
      try {{
        const networks = await jsonFetch('/api/wifi/scan');
        select.innerHTML = '';
        if (networks.length === 0) {{
          select.innerHTML = '<option value="">Сети не найдены</option>';
        }} else {{
          networks.forEach((network) => {{
            const option = document.createElement('option');
            option.value = network.ssid;
            option.textContent = network.ssid + ' · ' + network.signal + '% · ' + network.security;
            select.appendChild(option);
          }});
        }}
        message.textContent = 'Готово. Выбери сеть.';
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('connectButton').addEventListener('click', async () => {{
      const message = document.getElementById('wifiMessage');
      message.textContent = 'Подключаюсь...';
      try {{
        const result = await jsonFetch('/api/wifi/connect', {{
          method: 'POST',
          body: JSON.stringify({{
            ssid: document.getElementById('ssid').value,
            password: document.getElementById('wifiPassword').value
          }})
        }});
        message.textContent = result.message;
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('apButton').addEventListener('click', async () => {{
      const message = document.getElementById('wifiMessage');
      message.textContent = 'Включаю setup-сеть...';
      try {{
        const result = await jsonFetch('/api/setup/access-point', {{ method: 'POST', body: '{{}}' }});
        message.textContent = result.message;
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    async function refreshUpdateStatus() {{
      try {{
        const payload = await jsonFetch('/api/update/status');
        renderUpdateStatus(payload);
      }} catch (error) {{
        document.getElementById('updateMessage').textContent = error.message;
      }}
    }}

    function renderUpdateStatus(payload) {{
      const status = payload.status || {{}};
      const stable = payload.stable_build || {{}};
      const result = payload.last_result || {{}};
      document.getElementById('updateCurrent').textContent = shortCommit(status.current);
      document.getElementById('updateRemote').textContent = shortCommit(status.upstream);
      document.getElementById('updateStable').textContent = shortCommit(stable.commit || status.stable) || 'не сохранен';
      document.getElementById('updateJob').textContent = payload.running ? payload.action : 'idle';
      document.getElementById('updateMessage').textContent = payload.running ? 'Работаю: ' + payload.action : (result.message || status.message || 'Готово.');
    }}

    async function runUpdateAction(url, text) {{
      if (!confirm(text)) return;
      document.getElementById('updateMessage').textContent = 'Запускаю...';
      try {{
        const payload = await jsonFetch(url, {{ method: 'POST', body: '{{}}' }});
        renderUpdateStatus(payload);
      }} catch (error) {{
        document.getElementById('updateMessage').textContent = error.message;
      }}
    }}

    document.getElementById('checkUpdateButton').addEventListener('click', async () => {{
      document.getElementById('updateMessage').textContent = 'Проверяю GitHub...';
      try {{
        const payload = await jsonFetch('/api/update/check', {{ method: 'POST', body: '{{}}' }});
        renderUpdateStatus(payload);
      }} catch (error) {{
        document.getElementById('updateMessage').textContent = error.message;
      }}
    }});

    document.getElementById('applyUpdateButton').addEventListener('click', () => {{
      runUpdateAction('/api/update/apply', 'Скачать и применить новую версию? Текущий build станет стабильным rollback build.');
    }});

    document.getElementById('rollbackButton').addEventListener('click', () => {{
      runUpdateAction('/api/update/rollback', 'Откатиться на сохраненную стабильную версию? Робот перезапустится.');
    }});

    window.setInterval(refreshUpdateStatus, 2500);
    refreshUpdateStatus();

    document.getElementById('bluetoothScanButton').addEventListener('click', async () => {{
      const message = document.getElementById('bluetoothMessage');
      const select = document.getElementById('bluetoothDevice');
      message.textContent = 'Ищу пульты...';
      try {{
        const devices = await jsonFetch('/api/bluetooth/scan');
        select.innerHTML = '';
        if (devices.length === 0) {{
          select.innerHTML = '<option value="">Пульты не найдены</option>';
          message.textContent = 'Ничего не нашел. Проверь pairing mode.';
        }} else {{
          devices.forEach((device) => {{
            const option = document.createElement('option');
            const state = device.connected ? ' · подключен' : (device.paired ? ' · знакомый' : '');
            option.value = device.address;
            option.textContent = device.name + ' · ' + device.address + state;
            select.appendChild(option);
          }});
          message.textContent = 'Готово. Выбери пульт.';
        }}
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('bluetoothConnectButton').addEventListener('click', async () => {{
      const message = document.getElementById('bluetoothMessage');
      message.textContent = 'Подключаю пульт...';
      try {{
        const result = await jsonFetch('/api/bluetooth/connect', {{
          method: 'POST',
          body: JSON.stringify({{ address: document.getElementById('bluetoothDevice').value }})
        }});
        message.textContent = result.message;
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('bluetoothDisconnectButton').addEventListener('click', async () => {{
      const message = document.getElementById('bluetoothMessage');
      message.textContent = 'Отключаю пульт...';
      try {{
        const result = await jsonFetch('/api/bluetooth/disconnect', {{
          method: 'POST',
          body: JSON.stringify({{ address: document.getElementById('bluetoothDevice').value }})
        }});
        message.textContent = result.message;
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('saveKeyButton').addEventListener('click', async () => {{
      const message = document.getElementById('keyMessage');
      message.textContent = 'Сохраняю...';
      try {{
        const result = await jsonFetch('/api/openai-key', {{
          method: 'POST',
          body: JSON.stringify({{ api_key: document.getElementById('apiKey').value }})
        }});
        document.getElementById('apiKey').value = '';
        message.textContent = 'Сохранено: ' + result.masked;
      }} catch (error) {{
        message.textContent = error.message;
      }}
    }});

    document.getElementById('checkKeyButton').addEventListener('click', async () => {{
      const message = document.getElementById('keyMessage');
      const box = document.getElementById('limitBox');
      message.textContent = 'Проверяю ключ...';
      box.innerHTML = '<div><strong>Лимиты:</strong> спрашиваю OpenAI...</div>';
      try {{
        const result = await jsonFetch('/api/openai-key/check', {{
          method: 'POST',
          body: '{{}}'
        }});
        const limits = result.rate_limits || {{}};
        message.textContent = result.message;
        box.innerHTML = [
          '<div><strong>Модель:</strong> ' + escapeHtml(result.model || 'unknown') + '</div>',
          '<div><strong>Requests:</strong> ' + escapeHtml(limits.remaining_requests || '?') + ' осталось из ' + escapeHtml(limits.limit_requests || '?') + '</div>',
          '<div><strong>Tokens:</strong> ' + escapeHtml(limits.remaining_tokens || '?') + ' осталось из ' + escapeHtml(limits.limit_tokens || '?') + '</div>',
          '<div><strong>Reset:</strong> requests ' + escapeHtml(limits.reset_requests || '?') + ', tokens ' + escapeHtml(limits.reset_tokens || '?') + '</div>',
          '<div class="small">Request ID: ' + escapeHtml(result.request_id || 'нет') + '</div>',
          '<div class="small">' + escapeHtml(result.billing_note || '') + '</div>'
        ].join('');
      }} catch (error) {{
        message.textContent = error.message;
        box.innerHTML = '<div><strong>Лимиты:</strong> проверка не получилась.</div>';
      }}
    }});

    function escapeHtml(value) {{
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    function shortCommit(value) {{
      value = String(value || '');
      return value ? value.slice(0, 7) : '';
    }}
  </script>
</body>
</html>
"""


def _render_debug_page() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Picar Debug</title>
  <style>
    :root {
      --ink: #161b22;
      --muted: #687389;
      --line: #d7dde7;
      --paper: #f7fafc;
      --panel: #ffffff;
      --sky: #2f80ed;
      --mint: #1f9d76;
      --sun: #f4b740;
      --coral: #ef6f5e;
      --violet: #7c5cff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: linear-gradient(180deg, #f9fbff 0%, #eef7f3 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell { max-width: 1180px; margin: 0 auto; padding: 20px; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 2px solid rgba(22,27,34,.08); }
    h1 { margin: 0; font-size: 32px; letter-spacing: 0; }
    h2 { margin: 0 0 10px; font-size: 20px; letter-spacing: 0; }
    a { color: var(--sky); font-weight: 800; text-decoration: none; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
    section { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.88); padding: 14px; box-shadow: 0 10px 22px rgba(26,35,50,.08); }
    .wide { grid-column: 1 / -1; }
    .badge { display: inline-flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 8px; background: #fff; border: 1px solid var(--line); font-weight: 800; }
    .dot { width: 10px; height: 10px; border-radius: 99px; background: var(--coral); }
    .dot.live { background: var(--mint); }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .stat { background: #f7fbff; border-left: 4px solid var(--sky); border-radius: 6px; padding: 10px; min-height: 58px; }
    .stat strong { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .controller-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .button-cell { min-height: 42px; border: 1px solid var(--line); border-radius: 8px; display: grid; place-items: center; font-weight: 900; background: #fff; }
    .button-cell.on { background: var(--sun); color: #241b00; border-color: #d79a20; }
    canvas { width: 100%; display: block; border: 1px solid var(--line); border-radius: 8px; background: #101828; }
    #stickCanvas { height: 230px; }
    #waveCanvas { height: 150px; }
    #logConsole { min-height: 260px; max-height: 360px; overflow: auto; margin: 0; padding: 12px; border-radius: 8px; background: #101828; color: #d7e6ff; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button { appearance: none; border: 0; border-radius: 8px; min-height: 38px; padding: 8px 12px; font-weight: 900; color: white; background: var(--ink); cursor: pointer; }
    button.secondary { background: var(--violet); }
    @media (max-width: 820px) {
      .grid, .stats { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
      .controller-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>Picar Debug</h1>
        <a href="/">← назад к setup</a>
      </div>
      <div class="badge"><span class="dot" id="wsDot"></span><span id="wsState">connecting</span></div>
    </header>

    <div class="grid">
      <section class="wide">
        <h2>Состояние</h2>
        <div class="stats">
          <div class="stat"><strong>Пульт</strong><span id="controllerName">?</span></div>
          <div class="stat"><strong>Скорость</strong><span id="driveSpeed">0</span></div>
          <div class="stat"><strong>Руль</strong><span id="driveSteering">0</span></div>
        </div>
      </section>

      <section>
        <h2>Кнопки</h2>
        <div class="controller-grid" id="controllerGrid"></div>
      </section>

      <section>
        <h2>Стики</h2>
        <canvas id="stickCanvas" width="720" height="260"></canvas>
      </section>

      <section>
        <div class="row" style="justify-content: space-between; margin-bottom: 10px">
          <h2 style="margin: 0">Звуковая волна</h2>
          <button class="secondary" id="micButton" type="button">Микрофон браузера</button>
        </div>
        <canvas id="waveCanvas" width="720" height="180"></canvas>
      </section>

      <section>
        <h2>События</h2>
        <pre id="eventConsole"></pre>
      </section>

      <section class="wide">
        <h2>Консоль</h2>
        <pre id="logConsole"></pre>
      </section>
    </div>
  </main>

  <script>
    const buttons = ['a','b','x','y','l1','r1','l2','r2','select','start'];
    const controllerGrid = document.getElementById('controllerGrid');
    buttons.forEach((name) => {
      const div = document.createElement('div');
      div.className = 'button-cell';
      div.id = 'button-' + name;
      div.textContent = name.toUpperCase();
      controllerGrid.appendChild(div);
    });

    let lastPayload = null;
    let waveMode = 'idle';
    let analyser = null;
    let audioData = null;

    function connectDebugSocket() {
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
      const socket = new WebSocket(protocol + '://' + location.host + '/ws/debug');
      socket.onopen = () => setWsState(true, 'live');
      socket.onclose = () => {
        setWsState(false, 'reconnect');
        window.setTimeout(connectDebugSocket, 700);
      };
      socket.onerror = () => setWsState(false, 'error');
      socket.onmessage = (event) => {
        lastPayload = JSON.parse(event.data);
        renderPayload(lastPayload);
      };
    }

    function setWsState(live, text) {
      document.getElementById('wsDot').classList.toggle('live', live);
      document.getElementById('wsState').textContent = text;
    }

    function renderPayload(payload) {
      const controller = payload.controller || {};
      const drive = payload.drive || {};
      document.getElementById('controllerName').textContent = controller.connected ? controller.name : 'не подключен';
      document.getElementById('driveSpeed').textContent = drive.speed ?? 0;
      document.getElementById('driveSteering').textContent = drive.steering_angle ?? 0;

      const named = controller.named_buttons || {};
      buttons.forEach((name) => {
        document.getElementById('button-' + name).classList.toggle('on', Boolean(named[name]));
      });

      document.getElementById('eventConsole').textContent = (payload.events || [])
        .slice(-14)
        .map((item) => item.button + ' · ' + item.event)
        .join('\\n');
      document.getElementById('logConsole').textContent = (payload.logs || [])
        .slice(-80)
        .map((item) => '[' + item.level + '] ' + item.logger + ': ' + item.message)
        .join('\\n');
      drawSticks(controller.axes || {});
    }

    function drawSticks(axes) {
      const canvas = document.getElementById('stickCanvas');
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawStick(ctx, 180, 130, Number(axes['0'] || 0), Number(axes['1'] || 0), 'left');
      drawStick(ctx, 540, 130, Number(axes['2'] || 0), Number(axes['3'] || 0), 'right');
    }

    function drawStick(ctx, cx, cy, x, y, label) {
      ctx.strokeStyle = '#7c8aa5';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(cx, cy, 82, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = '#2f80ed';
      ctx.beginPath();
      ctx.arc(cx + x * 70, cy + y * 70, 18, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#d7e6ff';
      ctx.font = '18px system-ui';
      ctx.fillText(label, cx - 22, cy + 110);
    }

    document.getElementById('micButton').addEventListener('click', async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const context = new AudioContext();
        const source = context.createMediaStreamSource(stream);
        analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        source.connect(analyser);
        audioData = new Uint8Array(analyser.fftSize);
        waveMode = 'browser';
      } catch (error) {
        waveMode = 'idle';
      }
    });

    function drawWave() {
      const canvas = document.getElementById('waveCanvas');
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = waveMode === 'browser' ? '#1f9d76' : '#f4b740';
      ctx.lineWidth = 3;
      ctx.beginPath();
      if (analyser && audioData) {
        analyser.getByteTimeDomainData(audioData);
        audioData.forEach((value, index) => {
          const x = index / audioData.length * canvas.width;
          const y = value / 255 * canvas.height;
          index === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
      } else {
        const now = Date.now() / 260;
        for (let x = 0; x < canvas.width; x += 8) {
          const y = canvas.height / 2 + Math.sin(x / 24 + now) * 18;
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
      requestAnimationFrame(drawWave);
    }

    connectDebugSocket();
    drawWave();
  </script>
</body>
</html>
"""


def _render_photo_card(path: Path) -> str:
    name = html.escape(path.name)
    url = f"/photos/{name}"
    size_kb = max(1, round(path.stat().st_size / 1024))
    return f"""
<article class="photo-card">
  <a href="{url}"><img src="{url}" alt="Фото {name}"></a>
  <div class="photo-body">
    <div class="photo-name">{name}</div>
    <div class="small">{size_kb} KB</div>
    <div class="row photo-actions">
      <a class="button secondary" download href="{url}"><span aria-hidden="true">↓</span> Скачать</a>
      <button class="danger" type="button" data-delete-photo="{name}"><span aria-hidden="true">×</span> Удалить</button>
    </div>
  </div>
</article>
"""
