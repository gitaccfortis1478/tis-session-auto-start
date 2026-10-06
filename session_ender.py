import rich
import time
from datetime import datetime
import argparse
import pandas as pd
from enum import Enum
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from chrome_window_closer import close_chrome_for_profile
import constant_details
from constant_details import CSSClassName
from utilities import log_details, start_logging, complete_logging


SELENIUM_PROFILE = constant_details.SELENIUM_PROFILE

SESSIONS_URL = constant_details.SESSIONS_URL

SESSION_ENDER_ARGUMENT_NAME = constant_details.SESSION_ENDER_ARGUMENT_NAME

# How long we give the frontend to render session data.
SESSION_LOAD_TIMEOUT = constant_details.SESSION_LOAD_TIMEOUT


def create_driver():
    close_chrome_for_profile(SELENIUM_PROFILE)
    
    options = webdriver.ChromeOptions()

    options.add_argument(f"--user-data-dir={SELENIUM_PROFILE}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--start-maximized")
    # options.add_experimental_option("detach", True)

    return webdriver.Chrome(options=options)


# ============================================================
# Helper functions
# ============================================================

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


def select_in_progress(driver: WebDriver, wait: WebDriverWait):
    """Select the In Progress sessions tab."""

    log_details(
        "[cyan]Checking for sessions currently in progress...[/cyan]"
    )

    in_progress_button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[starts-with(normalize-space(.), 'In Progress')]"
            )
        )
    )

    in_progress_button.click()

    log_details(
        "[yellow]In Progress selected. Waiting for sessions to load...[/yellow]"
    )


def resume_session(driver: WebDriver, session_card: WebElement):
    """Resume an existing session."""

    log_details(
        "\n[bold cyan]━━━ Ongoing Session Found ━━━[/bold cyan]"
    )

    log_details(session_card.text)

    log_details(
        "[yellow]Looking for Resume button...[/yellow]"
    )

    resume_button = session_card.find_element(
        By.XPATH,
        ".//button[contains(normalize-space(.), 'Resume')]"
    )

    log_details(
        "[yellow]Resuming session...[/yellow]"
    )

    resume_button.click()

    log_details(
        "[bold green]✓ Session resumed successfully![/bold green]"
    )

    log_details(
        "[bold yellow]Browser will remain open for the user.[/bold yellow]"
    )

    input(
        "\nPress Enter when you are finished with the session..."
    )


def end_session(driver: WebDriver, wait: WebDriverWait, session_card: WebElement, what_was_covered: str | None = None, to_do_before_next_session: str | None = None):
    """End an existing session."""

    log_details(
        "\n[bold cyan]━━━ Ongoing Session Found ━━━[/bold cyan]"
    )

    log_details(session_card.text)

    log_details(
        "[yellow]Looking for Resume button...[/yellow]"
    )

    resume_button = session_card.find_element(
        By.XPATH,
        ".//button[contains(normalize-space(.), 'Resume')]"
    )

    log_details(
        "[yellow]Resuming session...[/yellow]"
    )

    resume_button.click()

    research_chips = driver.find_elements(
        By.XPATH,
        "//span[contains(@class, 'conduct-chip') and contains(normalize-space(.), 'Research')]"
    )

    if research_chips:
        proceed_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[starts-with(normalize-space(.), 'Proceed')]")
            )
        )

        proceed_button.click()

        submit_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[starts-with(normalize-space(.), 'Submit')]")
            )
        )

        submit_button.click()

    else:
        rows = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "tr.conduct-student-row")
            )
        )

        for row in rows:
            present_button = row.find_element(
                By.XPATH,
                ".//button[normalize-space(.)='Present']"
            )
            wait.until(lambda d: present_button.is_displayed() and present_button.is_enabled())
            present_button.click()

        wrap_up_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space(.)='Continue to Wrap Up']")
            )
        )

        wrap_up_button.click()
        
        lesson_notes = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'textarea[placeholder*="lesson notes"]')
            )
        )
        
        lesson_notes.clear()
        
        if what_was_covered:
            lesson_notes.send_keys(what_was_covered)
        
        next_session_assignments = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'textarea[placeholder*="next session"]')
            )
        )
        
        next_session_assignments.clear()
        
        if to_do_before_next_session:
            next_session_assignments.send_keys(to_do_before_next_session)

        submit_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[starts-with(normalize-space(.), 'Submit')]")
            )
        )

        submit_button.click()

    log_details(
        "[green]Session ended successfully.[/green]"
    )



def main():
    start_logging()
    
    parser = argparse.ArgumentParser()
    parser.add_argument(SESSION_ENDER_ARGUMENT_NAME, type=int, required=False)
    
    args = parser.parse_args()
    
    send_details_for_session_id = args.session_id_for_message
    
    what_was_covered = None
    to_do_before_next_session = None
    
    try:
        today = datetime.now()
        
        schedule_dir = constant_details.BASE_DIR / "upcoming_schedules"
        schedule_dir.mkdir(parents=True, exist_ok=True)
    
        schedule_with_messages_filename = f"message-for-{today:%Y-%m-%d}.csv"
        schedule_with_messages_path = schedule_dir / schedule_with_messages_filename
    
        df = pd.read_csv(schedule_with_messages_path)
    
        matches = df[df["ID"] == send_details_for_session_id]
        
        session_to_send_details_of_while_ending = matches.iloc[0] if not matches.empty else None
        
        if session_to_send_details_of_while_ending is not None:
            what_was_covered = session_to_send_details_of_while_ending["What Was Covered"]
            to_do_before_next_session = session_to_send_details_of_while_ending["To Do Before Next Session"]
            
            what_was_covered = None if pd.isna(what_was_covered) else what_was_covered
            to_do_before_next_session = None if pd.isna(to_do_before_next_session) else to_do_before_next_session
    
            if ((what_was_covered is not None) and (len(what_was_covered) > 200)):
                log_details("\n[bold red]What Was Covered text length exceeds 200 characters. Dropping...[/bold red]")
                what_was_covered = None
    
            if ((to_do_before_next_session is not None) and (len(to_do_before_next_session) > 200)):
                log_details("\n[bold red]To Do Before Next Session text length exceeds 200 characters. Dropping...[/bold red]")
                to_do_before_next_session = None
    
    except Exception as e:
        log_details(f"Some exception occurred while reading {schedule_with_messages_filename}: {e}")
    
    log_details(f"{what_was_covered = }")
    log_details(f"{to_do_before_next_session = }")
 
    driver = create_driver()
    wait = WebDriverWait(driver, 30)
    
    # This controls whether finally() closes Chrome.
    keep_browser_open = False

    try:

        # ----------------------------------------------------
        # 1. Open sessions page
        # ----------------------------------------------------
        
        open_sessions_page(driver, wait)
        
        # ----------------------------------------------------
        # 2. Check for sessions currently in progress
        # ----------------------------------------------------

        select_in_progress(driver, wait)

        # IMPORTANT:
        # React/Vue/etc. may still be fetching the sessions even
        # though document.readyState is already "complete".
        in_progress_cards = wait_for_session_cards(driver)
        
        # ----------------------------------------------------
        # 3. If an ongoing session exists, end it
        # ----------------------------------------------------

        if in_progress_cards:

            session_card = in_progress_cards[0]

            end_session(
                driver=driver, 
                wait=wait, 
                session_card=session_card,
                what_was_covered=what_was_covered,
                to_do_before_next_session=to_do_before_next_session
            )

            # keep_browser_open = True

    except Exception as e:

        log_details(
            f"\n[bold red]✗ An error occurred:[/bold red] {e}"
        )

        # Keep Chrome open so you can inspect what happened.
        keep_browser_open = True

        raise e

    finally:

        if keep_browser_open:

            log_details(
                "\n[bold yellow]Browser left open.[/bold yellow]"
            )

            input("Press enter to close")

        else:

            log_details(
                "[dim]Closing browser...[/dim]"
            )

            driver.quit()
            
        complete_logging()


if __name__ == "__main__":
    main()