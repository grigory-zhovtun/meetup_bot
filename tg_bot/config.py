from environs import Env


env = Env()
env.read_env()

# Опциональное чтение токена - может быть не установлен для веб-сервиса
TELEGRAM_BOT_TOKEN = env.str('TG_TOKEN', default=None)
