from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from pathlib import Path


def make_driver(user_data_dir="./chrome_profile", headless=False):
    opts = Options()
    opts.add_argument(f"--user-data-dir={Path(user_data_dir).resolve()}")  # giữ cookie đăng nhập
    opts.add_argument("--lang=vi")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--start-maximized")
    if headless:
        opts.add_argument("--headless=new")
    return webdriver.Chrome(options=opts)


def is_checkpoint(driver):
    u = driver.current_url
    return (any(x in u for x in ("checkpoint", "login", "two_step_verification"))
            or bool(driver.find_elements(By.CSS_SELECTOR, "input[name='email'], input[name='pass']")))


if __name__ == "__main__":  # chạy 1 lần để login thủ công
    d = make_driver()
    d.get("https://www.facebook.com/")
    input("Đăng nhập xong thì nhấn Enter...")
    d.quit()
