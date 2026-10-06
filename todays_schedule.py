import time
from enum import Enum
import rich
from datetime import datetime
from pathlib import Path
import pandas as pd
import subprocess
import shutil

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from chrome_window_closer import close_chrome_for_profile
import constant_details

from constant_details import CSSClassName
from utilities import log_details, empty_directory


SELENIUM_PROFILE = constant_details.SELENIUM_PROFILE

SESSIONS_URL = constant_details.SESSIONS_URL

# How long we give the frontend to render session data.
SESSION_LOAD_TIMEOUT = constant_details.SESSION_LOAD_TIMEOUT


def create_driver():
    close_chrome_for_profile(SELENIUM_PROFILE)
    
    options = webdriver.ChromeOptions()

    options.add_argument(f"--user-data-dir={SELENIUM_PROFILE}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--headless=new")

    return webdriver.Chrome(options=options)


def wait_for_page_load(driver: WebDriver, wait: WebDriverWait):
    """Wait until the browser reports that the document is loaded."""

    wait.until(
        lambda d: d.execute_script(
            "return document.readyState"
        ) == "complete"
    )


def get_session_cards(driver: WebDriver):
    """Return all currently rendered session cards."""

    return driver.find_elements(
        By.CSS_SELECTOR,
        CSSClassName.SESSION_CARD_CONTAINER.value,
    )


def wait_for_session_cards(
    driver: WebDriver,
    timeout=SESSION_LOAD_TIMEOUT,
):
    """
    Wait for the frontend to render session cards.

    Returns:
        list: session cards if found
        []: if no cards appeared before timeout
    """

    log_details(
        f"[dim]Waiting up to {timeout}s for session cards to render...[/dim]"
    )

    end_time = time.time() + timeout

    while time.time() < end_time:
        cards = get_session_cards(driver)

        if cards:
            log_details(
                f"[green]Found {len(cards)} session card(s).[/green]"
            )
            return cards

        # Check again shortly.
        time.sleep(0.5)

    log_details(
        "[yellow]No session cards appeared within the timeout.[/yellow]"
    )

    return []


def open_sessions_page(driver: WebDriver, wait: WebDriverWait):
    """Open the sessions page and wait for it to load."""

    log_details("[cyan]Opening TIS Mentor sessions...[/cyan]")

    driver.get(SESSIONS_URL)

    wait_for_page_load(driver, wait)

    log_details(
        f"[green]Page loaded:[/green] {driver.title}"
    )


def select_upcoming(driver: WebDriver, wait: WebDriverWait):
    """Select the Upcoming sessions tab."""

    log_details(
        "[green]No ongoing sessions found.[/green]"
    )

    log_details(
        "[cyan]Switching to Upcoming sessions...[/cyan]"
    )

    upcoming_sessions_button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[starts-with(normalize-space(.), 'Upcoming')]"
            )
        )
    )

    upcoming_sessions_button.click()

    log_details(
        "[yellow]Upcoming selected. Waiting for sessions to load...[/yellow]"
    )

def find_element_with_fallback(card: WebElement, primary_selector: str, fallback_selector: str) -> WebElement:
    try:
        return card.find_element(By.CSS_SELECTOR, primary_selector) 
    except Exception:
        return card.find_element(By.CSS_SELECTOR, fallback_selector)


def main():
    driver = create_driver()
    wait = WebDriverWait(driver, 30)
    
    # This controls whether finally() closes Chrome.
    keep_browser_open = False

    try:

        # ----------------------------------------------------
        # 1. Open sessions page
        # ----------------------------------------------------

        open_sessions_page(driver, wait)

        select_upcoming(driver, wait)

        upcoming_cards = wait_for_session_cards(driver)

        today = datetime.now()
        today_day = str(today.day)
        today_month = today.strftime("%b").upper()

        schedules = []
        schedules_with_messages = []

        for id, card in enumerate(upcoming_cards):

            date_block = card.find_element(
                By.CSS_SELECTOR,
                CSSClassName.SESSION_CARD_DATE_BLOCK.value
            )

            day = date_block.find_elements(By.TAG_NAME, "div")[1].text.strip()
            month = date_block.find_elements(By.TAG_NAME, "div")[2].text.strip()

            # Only keep sessions scheduled for today
            if day != today_day or month.upper() != today_month:
                continue

            student = card.find_element(
                By.CSS_SELECTOR,
                ".session-card-date-block + div > div:first-child > span:first-child"
            ).text.strip()

            time_span = find_element_with_fallback(
                card, 
                "span:has(> i.fa-clock)", 
                ".session-card-date-block + div > div:nth-child(3) > span:first-child"
            )

            course_span = find_element_with_fallback(
                card, 
                "span:has(> i.fa-graduation-cap)", 
                ".session-card-date-block + div > div:nth-child(3) > span:nth-child(2)"
            )

            time_text = time_span.text.strip()
            course = course_span.text.strip()

            # Example:
            # "4:30 PM - 6:00 PM (90 mins)"
            time_text = time_text.split("(")[0].strip()

            start_time, end_time = [
                time.strip()
                for time in time_text.split("-", 1)
            ]

            start_timestamp = datetime.strptime(
                f"{today.strftime('%Y-%m-%d')} {start_time}",
                "%Y-%m-%d %I:%M %p"
            )

            end_timestamp = datetime.strptime(
                f"{today.strftime('%Y-%m-%d')} {end_time}",
                "%Y-%m-%d %I:%M %p"
            )

            schedules.append({
                "ID": id,
                "Date": today.strftime("%Y-%m-%d"),
                "Student": student,
                "Course": course,
                "Start Time": start_timestamp,
                "End Time": end_timestamp,
            })

            schedules_with_messages.append({
                "ID": id,
                "Date": today.strftime("%Y-%m-%d"),
                "Student": student,
                "Course": course,
                "Start Time": start_timestamp,
                "End Time": end_timestamp,
                "What Was Covered": "",
                "To Do Before Next Session": ""
            })


        schedule_df = pd.DataFrame(
            schedules,
            columns=[
                "ID",
                "Date",
                "Student",
                "Course",
                "Start Time",
                "End Time"
            ]
        )

        schedule_with_messages_df = pd.DataFrame(
            schedules_with_messages,
            columns=[
                "ID",
                "Date",
                "Student",
                "Course",
                "Start Time",
                "End Time",
                "What Was Covered",
                "To Do Before Next Session"
            ]
        )


        schedule_dir = Path(__file__).parent / "upcoming_schedules"
        schedule_dir.mkdir(parents=True, exist_ok=True)

        schedule_filename = f"{today:%Y-%m-%d}.csv"
        schedule_path = schedule_dir / schedule_filename

        schedule_with_messages_filename = f"message-for-{today:%Y-%m-%d}.csv"
        schedule_with_messages_path = schedule_dir / schedule_with_messages_filename
        
        empty_directory(schedule_dir)

        schedule_df.to_csv(schedule_path, index=False)
        schedule_with_messages_df.to_csv(schedule_with_messages_path, index=False)

        log_details(schedule_df)
        log_details(f"\nSaved schedule to: {schedule_path}")


    except Exception as e:

        log_details(
            f"\n[bold red]✗ An error occurred:[/bold red] {e}"
        )

        # Keep Chrome open so you can inspect what happened.
        keep_browser_open = True

        raise e

    finally:

        pass

        # if keep_browser_open:

        #     log_details(
        #         "\n[bold yellow]Browser left open.[/bold yellow]"
        #     )

        # else:

        #     log_details(
        #         "[dim]Closing browser...[/dim]"
        #     )

        #     driver.quit()


if __name__ == "__main__":
    main()