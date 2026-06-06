"""Главный цикл KidBot."""

from __future__ import annotations

import logging
import signal
import threading
import time

from kidbot.core.ai_chat import AIChat
from kidbot.core.ai_vision import AIVision
from kidbot.core.camera import Camera
from kidbot.core.config import load_config, project_root, resolve_path
from kidbot.core.controller import ButtonTracker, ControllerReader, map_named_buttons
from kidbot.core.debug_state import DebugStateStore, attach_debug_log_handler
from kidbot.core.logger import setup_logging
from kidbot.core.media import MediaPlayer
from kidbot.core.network import NetworkMonitor
from kidbot.core.robot_hw import RobotHardware
from kidbot.core.safety import SafetyWatchdog
from kidbot.core.secrets import apply_env_file
from kidbot.core.smoothing import RateLimiter, Smoother
from kidbot.core.status import StatusTracker
from kidbot.core.updater import rollback_to_stable
from kidbot.core.voice import Voice
from kidbot.core.web_server import run_web_server
from kidbot.core.wifi_setup import AccessPointConfig, start_access_point
from kidbot.kid_code.button_actions import ButtonActionContext, ButtonActions
from kidbot.kid_code.drive_logic import build_drive_command, emergency_stop_command
from kidbot.kid_code.robot_personality import ready_sentence


def main() -> None:
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    config = load_config()
    env_path = project_root() / ".env"
    apply_env_file(env_path)
    _ensure_directories(config)

    log_dir = resolve_path(config, "logs")
    setup_logging(log_dir)
    debug_store = DebugStateStore()
    attach_debug_log_handler(debug_store)
    logger = logging.getLogger("kidbot")
    logger.info("KidBot starting")

    robot_config = config.get("robot", {})
    robot_name = robot_config.get("name", "KidBot")
    version = robot_config.get("version", "0.1.0")
    mock = bool(robot_config.get("mock", False))

    status = StatusTracker(robot_name=robot_name, version=version)
    voice = Voice(
        use_openai=bool(config.get("voice", {}).get("use_openai_tts", True)),
        espeak_voice=str(config.get("voice", {}).get("espeak_voice", "ru")),
        espeak_speed=int(config.get("voice", {}).get("espeak_speed", 150)),
        openai_model=str(config.get("openai", {}).get("tts_model", "gpt-4o-mini-tts")),
    )
    network_monitor = NetworkMonitor(speaker=voice.say)
    _refresh_network_status(status, network_monitor)
    _maybe_start_setup_access_point(config, status, logger, voice, mock)

    robot = RobotHardware(config=config, mock=mock)
    camera = Camera(photo_dir=resolve_path(config, "photos"), mock=mock)
    media = MediaPlayer(
        sounds_dir=resolve_path(config, "sounds"),
        music_dir=resolve_path(config, "music"),
        stories_dir=resolve_path(config, "stories"),
    )
    ai_chat = AIChat(config)
    ai_vision = AIVision(config)
    actions = ButtonActions(
        ButtonActionContext(
            robot=robot,
            camera=camera,
            voice=voice,
            media=media,
            ai_chat=ai_chat,
            ai_vision=ai_vision,
            status=status,
            photo_dir=resolve_path(config, "photos"),
        )
    )

    _start_web_server(config, status, logger, env_path, debug_store, camera)
    voice.say(ready_sentence(str(robot_name)))

    controller_config = config.get("controller", {})
    controller = ControllerReader(device_index=int(controller_config.get("device_index", 0)))
    button_tracker = ButtonTracker()
    watchdog = SafetyWatchdog(float(controller_config.get("watchdog_timeout_seconds", 1.0)))
    steering_smoother = Smoother(alpha=float(config.get("steering", {}).get("smoothing_alpha", 0.25)))
    speed_limiter = RateLimiter(
        rate_per_second=float(config.get("speed", {}).get("acceleration_per_second", 55)),
        initial_value=0.0,
    )

    poll_hz = max(1, int(controller_config.get("poll_hz", 30)))
    sleep_seconds = 1.0 / poll_hz
    front_sensor_config = config.get("front_sensor", {})
    front_sensor_interval = 1.0 / max(1, int(front_sensor_config.get("poll_hz", 5)))
    battery_config = config.get("battery", {})
    battery_interval = max(1.0, float(battery_config.get("poll_seconds", 5.0)))
    last_time = time.monotonic()
    last_network_check = 0.0
    last_front_sensor_check = 0.0
    last_battery_check = 0.0
    last_front_distance_cm = _record_front_sensor(robot, debug_store, config)
    controller_was_connected = False

    try:
        while not stop_event.is_set():
            now = time.monotonic()
            dt = now - last_time
            last_time = now

            if now - last_front_sensor_check >= front_sensor_interval:
                last_front_distance_cm = _record_front_sensor(robot, debug_store, config)
                last_front_sensor_check = now

            state = controller.poll()
            status.set_controller_connected(state.connected)
            named_buttons = _named_buttons(config, state)
            button_events = button_tracker.update(named_buttons)
            debug_store.record_controller(state, named_buttons, button_events)

            if state.connected:
                if not controller_was_connected:
                    logger.info("controller connected: %s", state.name)
                controller_was_connected = True
                watchdog.mark_controller_event()
                _drive_from_controller(
                    config,
                    state,
                    robot,
                    media,
                    steering_smoother,
                    speed_limiter,
                    dt,
                    debug_store,
                    last_front_distance_cm,
                )
                _move_head_from_dpad(config, state, robot, debug_store)
                _handle_button_events(button_events, actions)
                if button_tracker.combo_long_pressed("rollback", named_buttons, ("select", "start"), hold_seconds=2.0):
                    voice.say("Откатываюсь на стабильную версию.")
                    rollback_to_stable(project_root())
            else:
                if controller_was_connected:
                    robot.stop()
                    media.stop_engine_sound()
                    voice.say("Пульт потерялся. Я остановился.")
                    logger.warning("controller disconnected")
                controller_was_connected = False

            if watchdog.expired():
                robot.stop()
                media.stop_engine_sound()
                watchdog.stopped_due_to_timeout = True

            if now - last_battery_check >= battery_interval:
                _record_battery(robot, status)
                last_battery_check = now

            if now - last_network_check > 5.0:
                _refresh_network_status(status, network_monitor)
                last_network_check = now

            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("KidBot stopped by keyboard")
    except Exception as exc:
        status.set_error(exc)
        logger.exception("KidBot crashed")
        voice.say("У меня случилась ошибка. Я остановился.")
    finally:
        robot.emergency_stop()
        media.stop_all()
        camera.close()
        logger.info("KidBot shutdown complete")


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def request_stop(signum, frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


def _ensure_directories(config: dict) -> None:
    for key in ("photos", "logs", "sounds", "music", "stories"):
        resolve_path(config, key).mkdir(parents=True, exist_ok=True)


def _start_web_server(
    config: dict,
    status: StatusTracker,
    logger: logging.Logger,
    env_path,
    debug_store: DebugStateStore,
    camera: Camera,
) -> None:
    web_config = config.get("web", {})
    setup_ap_config = config.get("setup_ap", {})
    try:
        run_web_server(
            photo_dir=resolve_path(config, "photos"),
            status_provider=status.snapshot,
            host=str(web_config.get("host", "0.0.0.0")),
            port=int(web_config.get("port", 8080)),
            env_path=env_path,
            openai_model=str(config.get("openai", {}).get("chat_model", "gpt-5-mini")),
            repo_dir=project_root(),
            debug_store=debug_store,
            sounds_dir=resolve_path(config, "sounds"),
            capture_photo=camera.capture_photo,
            access_point_config=AccessPointConfig(
                ssid=str(setup_ap_config.get("ssid", "KidBot-Setup")),
                password=str(setup_ap_config.get("password", "kidbot1234")),
                interface=str(setup_ap_config.get("interface", "wlan0")),
                address=str(setup_ap_config.get("address", "192.168.4.1/24")),
            ),
        )
    except Exception as exc:
        status.set_error(exc)
        logger.error("web server did not start: %s", exc)


def _refresh_network_status(status: StatusTracker, network_monitor: NetworkMonitor) -> None:
    snapshot = network_monitor.check()
    status.set_network(snapshot.wifi_connected, snapshot.internet_connected, snapshot.ip_address)


def _record_front_sensor(robot: RobotHardware, debug_store: DebugStateStore, config: dict | None = None) -> float | None:
    distance_cm = robot.read_front_distance_cm()
    if distance_cm is None:
        status = "no-data"
    elif _front_obstacle_too_close(distance_cm, config or {}):
        status = "too-close"
    else:
        status = "ok"
    debug_store.record_front_sensor(distance_cm, status=status)
    return distance_cm


def _record_battery(robot: RobotHardware, status: StatusTracker) -> None:
    battery = robot.read_battery()
    status.set_battery(
        percentage=battery.get("percentage"),
        voltage=battery.get("voltage"),
        status=str(battery.get("status", "unknown")),
        source=str(battery.get("source", "")),
    )


def _maybe_start_setup_access_point(config: dict, status: StatusTracker, logger: logging.Logger, voice: Voice, mock: bool) -> None:
    setup_ap_config = config.get("setup_ap", {})
    if mock or not bool(setup_ap_config.get("enabled", True)) or not bool(setup_ap_config.get("auto_start_when_no_wifi", True)):
        return
    if status.snapshot().wifi_connected:
        return

    access_point = AccessPointConfig(
        ssid=str(setup_ap_config.get("ssid", "KidBot-Setup")),
        password=str(setup_ap_config.get("password", "kidbot1234")),
        interface=str(setup_ap_config.get("interface", "wlan0")),
        address=str(setup_ap_config.get("address", "192.168.4.1/24")),
    )
    result = start_access_point(access_point)
    if result.success:
        logger.info(result.message)
        voice.say(f"Я включил сеть {access_point.ssid}. Подключись к ней, чтобы настроить Wi-Fi.")
    else:
        logger.warning("setup access point failed: %s %s", result.message, result.stderr)


def _drive_from_controller(
    config: dict,
    state,
    robot: RobotHardware,
    media: MediaPlayer,
    steering_smoother: Smoother,
    speed_limiter: RateLimiter,
    dt: float,
    debug_store: DebugStateStore,
    front_distance_cm: float | None = None,
) -> None:
    controller_config = config.get("controller", {})
    axes = controller_config.get("axes", {})
    steering_axis = state.axis(int(axes.get("steering", 0)))
    throttle_axis = state.axis(int(axes.get("throttle", 3)))
    command = build_drive_command(steering_axis, throttle_axis, config)

    target_speed = command.speed
    current_speed = speed_limiter.value
    speed_config = config.get("speed", {})
    accelerating = abs(target_speed) > abs(current_speed) and target_speed * current_speed >= 0
    speed_limiter.rate_per_second = float(
        speed_config.get("acceleration_per_second" if accelerating else "braking_per_second", 70)
    )

    smooth_speed = speed_limiter.update(target_speed, dt)
    smooth_steering = steering_smoother.update(command.steering_angle)
    safe_speed = _safe_speed_for_front_sensor(smooth_speed, front_distance_cm, config)
    if safe_speed == 0.0 and smooth_speed > 0:
        speed_limiter.reset(0.0)
        smooth_speed = 0.0
    else:
        smooth_speed = safe_speed
    debug_store.record_drive(smooth_speed, smooth_steering)
    robot.drive(smooth_speed, smooth_steering)
    media.update_engine_sound(smooth_speed, config.get("engine_sound", {}))


def _safe_speed_for_front_sensor(speed: float, front_distance_cm: float | None, config: dict) -> float:
    if speed <= 0 or not _front_obstacle_too_close(front_distance_cm, config):
        return speed
    return 0.0


def _front_obstacle_too_close(front_distance_cm: float | None, config: dict) -> bool:
    if front_distance_cm is None:
        return False
    front_sensor_config = config.get("front_sensor", {})
    if isinstance(front_sensor_config, dict) and not bool(front_sensor_config.get("enabled", True)):
        return False
    stop_distance_cm = 10.0
    if isinstance(front_sensor_config, dict):
        stop_distance_cm = float(front_sensor_config.get("stop_distance_cm", stop_distance_cm))
    return 0 < float(front_distance_cm) <= stop_distance_cm


def _move_head_from_dpad(config: dict, state, robot: RobotHardware, debug_store: DebugStateStore) -> None:
    controller_config = config.get("controller", {})
    dpad_config = controller_config.get("dpad", {})
    hat_index = int(dpad_config.get("hat_index", 0))
    x, y = state.hat(hat_index)
    if x == 0 and y == 0:
        return
    step = float(config.get("head", {}).get("step", 5))
    pan_delta = x * step
    tilt_delta = y * step
    debug_store.record_head(pan_delta, tilt_delta)
    robot.move_head(pan_delta=pan_delta, tilt_delta=tilt_delta)


def _named_buttons(config: dict, state) -> dict[str, bool]:
    controller_config = config.get("controller", {})
    button_mapping = controller_config.get("buttons", {})
    return map_named_buttons(state, {name: int(index) for name, index in button_mapping.items()})


def _handle_button_events(button_events: list[tuple[str, str]], actions: ButtonActions) -> None:
    for name, event in button_events:
        if event not in {"press", "double", "long", "release"}:
            continue
        if name == "start" and event == "press":
            actions.press_start_stop_everything()
        elif name == "a" and event == "press":
            actions.press_a_take_photo()
        elif name == "b" and event == "press":
            actions.press_b_toggle_music()
        elif name == "x" and event == "press":
            actions.press_x_read_story()
        elif name == "y" and event == "press":
            actions.press_y_funny_vision()
        elif name == "y" and event == "double":
            actions.double_press_y_describe_scene()
        elif name == "y" and event == "long":
            actions.hold_y_explore_around()
        elif name == "select" and event == "press":
            actions.press_select_new_chat()
        elif name == "r1" and event == "press":
            actions.press_r1_status()
        elif name == "l1" and event == "release":
            actions.press_l1_push_to_talk()
        elif name == "l2" and event == "press":
            child_name = str(config.get("robot", {}).get("child_name", "")).strip() or "ребенок"
            actions.press_l2_find_thing(f"предмет, который попросил найти {child_name}")
        elif name == "r2" and event == "press":
            actions.press_r2_find_interesting()


if __name__ == "__main__":
    main()
