import schedule
import time
from main import run_agent

schedule.every().monday.at("09:00").do(run_agent)
schedule.every().tuesday.at("09:00").do(run_agent)

while True:
    schedule.run_pending()
    time.sleep(60)