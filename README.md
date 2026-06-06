# picar-kidbot

KidBot — Python-проект для робота SunFounder PiCar-X на Raspberry Pi 3B+.
Он умеет ездить от 8BitDo Lite 2 Bluetooth-геймпада, плавно рулить и менять
скорость, делать фото, показывать фото на простом сайте, говорить по-русски,
читать короткие истории, играть звуки и использовать OpenAI для чата, STT и
Vision, если есть интернет и переменная `OPENAI_API_KEY`.

В проекте есть две зоны кода:

- `kidbot/kid_code/` — простые файлы, которые можно читать ребенку вместе со взрослым.
- `kidbot/core/` — инфраструктура: железо, геймпад, веб, AI, логи, обновления.

## 1. Установка на Raspberry Pi

```bash
cd /home/pi
git clone <your-repo-url> picar-kidbot
cd picar-kidbot
chmod +x install.sh run.sh update.sh tools/generate_sample_audio.py
./install.sh
sudo systemctl start kidbot.service
```

Проверка на Mac или другом компьютере без робота:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 tools/generate_sample_audio.py
KIDBOT_MOCK=1 python3 -m kidbot.main
```

## 2. Подключение Bluetooth-пульта

Самый простой способ — через сайт KidBot:

1. Открой веб-интерфейс робота.
2. Включи pairing mode на Bluetooth-пульте.
3. В блоке `Пульт` нажми `Найти Bluetooth`.
4. Выбери пульт в списке.
5. Нажми `Подключить пульт`.

Если пульт уже знаком роботу, он обычно подключится сразу. Если это первое
подключение, держи пульт в pairing mode до конца подключения.

Ручной запасной способ на Raspberry Pi:

На Raspberry Pi:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
```

Переведи 8BitDo Lite 2 в режим Bluetooth pairing. Когда пульт появится:

```text
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
quit
```

У 8BitDo в разных режимах могут отличаться номера осей и кнопок. Перед первой
поездкой обязательно проверь маппинг.

## 3. Проверка кнопок и стиков

```bash
python3 -m tests.test_controller_print
```

Скрипт печатает:

- `axes`
- `buttons`
- `hats / dpad`
- сырые значения
- нормализованные значения

После проверки поправь `config.yaml`, если номера отличаются:

```yaml
controller:
  axes:
    steering: 0
    throttle: 3
  buttons:
    a: 0
    b: 1
```

## 4. Ручной запуск

На настоящем роботе:

```bash
python3 -m kidbot.main
```

Без железа:

```bash
KIDBOT_MOCK=1 python3 -m kidbot.main
```

Mock-режим нужен честно: он проверяет логику, фото, логи, веб-маршруты и код
кнопок, но не притворяется, что PiCar-X подключен.

## 5. Автостарт

`install.sh` устанавливает:

- `kidbot.service`
- `kidbot-updater.service`
- `kidbot-updater.timer` в выключенном состоянии

Полезные команды:

```bash
sudo systemctl enable kidbot.service
sudo systemctl start kidbot.service
sudo systemctl status kidbot.service
sudo systemctl restart kidbot.service
```

## 6. Где смотреть фото

Если работает hostname:

```text
http://picar.local:8080
```

Если hostname не открылся, нажми `R1` для статуса или выполни:

```bash
hostname -I
```

Потом открой:

```text
http://192.168.x.x:8080
```

Маршруты:

- `GET /`
- `GET /photos`
- `GET /photos/{filename}`
- `DELETE /api/photos/{filename}`
- `GET /api/status`
- `GET /api/photos`
- `GET /api/wifi/scan`
- `POST /api/wifi/connect`
- `POST /api/setup/access-point`
- `GET /api/bluetooth/scan`
- `POST /api/bluetooth/connect`
- `POST /api/bluetooth/disconnect`
- `GET /api/openai-key`
- `POST /api/openai-key`
- `POST /api/openai-key/check`
- `GET /api/update/status`
- `POST /api/update/check`
- `POST /api/update/apply`
- `POST /api/update/rollback`
- `GET /debug`
- `GET /ws/debug`

На главной странице можно:

- смотреть последние фото
- скачивать фото
- удалять фото
- сканировать Wi-Fi сети
- выбрать сеть и ввести пароль
- включить setup-сеть вручную
- найти и подключить Bluetooth-пульт
- сохранить `OPENAI_API_KEY`
- проверить, что `OPENAI_API_KEY` работает
- посмотреть remaining requests/tokens из OpenAI rate-limit headers, если OpenAI вернул эти headers
- вручную проверить и скачать обновление из GitHub
- откатиться на стабильную версию, если обновление не понравилось

Debug-страница:

```text
http://picar.local:8080/debug
```

Она показывает live-состояние пульта, кнопки, стики, последние события, логи и
звуковую волну. Данные пульта и логов идут по WebSocket `/ws/debug` с маленькой
задержкой. Кнопка `Микрофон браузера` рисует волну с микрофона устройства, на
котором открыт сайт; отдельный robot-mic backend можно добавить позже.

## 6.1 Setup-сеть как у умных камер

Если робот загрузился и не нашел Wi-Fi, он попробует включить точку доступа:

```text
KidBot-Setup
```

Пароль по умолчанию:

```text
kidbot1234
```

Подключись к этой сети с телефона или ноутбука и открой:

```text
http://192.168.4.1:8080
```

Там можно выбрать домашнюю Wi-Fi сеть, ввести пароль и сохранить OpenAI API key.
После подключения к домашнему Wi-Fi робот снова будет доступен по обычному IP.

Настройки setup-сети лежат в `config.yaml`:

```yaml
setup_ap:
  enabled: true
  auto_start_when_no_wifi: true
  ssid: "KidBot-Setup"
  password: "kidbot1234"
  interface: "wlan0"
  address: "192.168.4.1/24"
```

Для режима точки доступа используется NetworkManager и `nmcli`. `install.sh`
ставит `network-manager`, включает сервис и добавляет ограниченное sudo-правило,
чтобы веб-интерфейс мог запускать `nmcli` без пароля.

## 7. Кнопки

- `A`: сделать фото и сказать “Фотография готова!”
- `B`: включить или остановить случайную музыку
- `X`: прочитать короткую русскую историю
- `Y`: сделать фото и смешно, но доброжелательно описать сцену
- двойное `Y`: спокойно описать сцену
- удержание `Y`: посмотреть влево, вперед, вправо и дать обзор
- `Select`: очистить историю разговора
- `Start`: аварийно остановить движение, голос и музыку
- `L1`: push-to-talk, если доступен OpenAI
- `R1`: проговорить статус робота
- `L2`: искать предмет с подсказкой
- `R2`: найти что-нибудь интересное

## 8. OpenAI

Ключ нельзя хранить в репозитории.

```bash
export OPENAI_API_KEY="sk-..."
python3 -m kidbot.main
```

Ключ также можно ввести через веб-интерфейс KidBot. Он сохраняется в локальный
файл `.env` с правами `600`; этот файл добавлен в `.gitignore`.

В веб-интерфейсе есть кнопка `Проверить ключ`. Она делает маленький тестовый
запрос к OpenAI и показывает:

- работает ли ключ
- какая модель проверялась
- `x-request-id`
- сколько осталось requests/tokens до rate limit reset, если эти headers пришли

Важно: это не показывает денежный баланс аккаунта. Баланс, месячный spend и
подробный organization usage обычным robot API key не видны; для этого нужен
OpenAI admin key или dashboard.

Если ключа нет, KidBot все равно ездит, фотографирует, открывает веб-страницу,
играет звуки, читает истории и говорит через `espeak-ng`. Chat, STT и Vision
заменяются дружелюбными offline-фразами.

## 9. Логи

Файлы лежат в `logs/`:

- `kidbot.log`
- `errors.log`
- `controller.log`
- `network.log`
- `ai.log`

Смотреть systemd-логи:

```bash
journalctl -u kidbot.service -f
```

Смотреть локальные логи:

```bash
tail -f logs/kidbot.log logs/errors.log
```

## 10. Обновление

Обновления не скачиваются автоматически при включении робота. Это важно:
плохой commit не должен неожиданно приехать во время обычного запуска.

Открой сайт робота и используй блок `Обновления`:

- `Проверить` — сделать `git fetch` и показать, есть ли новый commit.
- `Обновить` — сохранить текущий commit как стабильный, сделать
  `git pull --ff-only`, обновить зависимости и перезапустить сервис.
- `Откатиться` — вернуться к сохраненному стабильному commit.

Стабильный build хранится локально:

```text
.kidbot/stable-build.json
```

Файл добавлен в `.gitignore`.

Скрипт `update.sh` оставлен как ручной запасной инструмент:

```bash
./update.sh
```

`install.sh` отключает `kidbot-updater.timer`, чтобы обновления не запускались
при boot и раз в сутки. Проверить это можно так:

```bash
sudo systemctl status kidbot-updater.timer
sudo systemctl list-timers kidbot-updater.timer
```

Аварийный rollback без сайта: зажми `Select` и `Start` на пульте примерно на 2
секунды. Это откатит робота на сохраненную стабильную версию и перезапустит
сервис.

Чтобы робот мог обновляться из GitHub/другого remote, на Raspberry Pi должен
быть настроен `origin` и upstream:

```bash
git remote add origin <repo-url>
git push -u origin main
```

Для приватного GitHub repo удобнее всего дать роботу read-only deploy key.
На Raspberry Pi:

```bash
ssh-keygen -t ed25519 -C "kidbot-pi" -f ~/.ssh/kidbot_github -N ""
cat ~/.ssh/kidbot_github.pub
```

Скопируй публичный ключ в GitHub: repo `Settings` → `Deploy keys` →
`Add deploy key`. Write access не нужен, если робот только скачивает обновления.

Потом настрой SSH-алиас:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com-kidbot
  HostName github.com
  User git
  IdentityFile ~/.ssh/kidbot_github
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
ssh -T git@github.com-kidbot
```

Клонирование или перевод существующего checkout на private repo:

```bash
git clone git@github.com-kidbot:knovikov/picar.git picar-kidbot
cd picar-kidbot
git remote set-url origin git@github.com-kidbot:knovikov/picar.git
git branch --set-upstream-to=origin/main main
```

После этого web update и `./update.sh` смогут делать `git fetch` /
`git pull --ff-only` без ввода GitHub password.

## 11. Если пропал интернет

KidBot должен сказать один раз:

```text
Интернет пропал. Я все еще умею ездить, фотографировать и шутить простыми шутками.
```

Когда интернет вернется:

```text
Интернет вернулся. Мой ум снова подключен к облакам.
```

`kidbot/core/network.py` специально отделен от остального кода, чтобы сеть,
камера, езда и сайт не мешали друг другу.

## 12. Если пульт не подключается

Сначала попробуй через сайт: блок `Пульт` → `Найти Bluetooth` →
`Подключить пульт`.

Проверь Bluetooth:

```bash
bluetoothctl devices
bluetoothctl info XX:XX:XX:XX:XX:XX
```

Проверь joystick-устройство:

```bash
ls -l /dev/input/js*
jstest /dev/input/js0
```

Потом запусти:

```bash
python3 -m tests.test_controller_print
```

Если номера кнопок или стиков отличаются, поменяй `config.yaml`.

## 13. Если камера не работает

Проверь, видит ли Raspberry Pi камеру:

```bash
libcamera-hello --list-cameras
python3 -m tests.test_camera
```

Если проверка идет не на Raspberry Pi:

```bash
KIDBOT_MOCK=1 python3 -m tests.test_camera
```

## 14. Тестовые команды

```bash
python3 -m tests.test_controller_print
python3 -m tests.test_drive
python3 -m tests.test_camera
python3 -m tests.test_voice
python3 -m tests.test_web_server
```

Все автоматические behavior-тесты:

```bash
python3 -m unittest tests.test_drive tests.test_camera tests.test_voice tests.test_web_server -v
```
