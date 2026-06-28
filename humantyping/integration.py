from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np

from .config import MIN_DWELL_TIME, TIME_DWELL_MEAN, TIME_DWELL_STD
from .typer import MarkovTyper


def _extract_char(action: str) -> str:
    """Extract the typed character(s) from an action string like TYPED 'x' or TYPED_SWAP 'ht'."""
    first_quote = action.index("'")
    last_quote = action.rindex("'")
    return action[first_quote + 1:last_quote]


def _typing_history(text: str, wpm: float, layout: str) -> list[tuple[float, str, str]]:
    """Plan the keystroke history for ``text`` once; shared by every adapter."""
    if not isinstance(text, str) or len(text) == 0:
        raise ValueError("text must be a non-empty string")
    typer = MarkovTyper(text, target_wpm=wpm, layout=layout)
    _, history = typer.run()
    return history


def _dwell_ms() -> float:
    """Key hold duration (keydown->keyup) in milliseconds, sampled per keystroke.

    Real keystrokes hold each key ~90ms, and keystroke-dynamics detectors read
    this dwell as much as inter-key timing. Playwright's ``press(delay=)`` takes
    milliseconds; the typing model works in seconds.
    """
    seconds = max(MIN_DWELL_TIME, float(np.random.normal(TIME_DWELL_MEAN, TIME_DWELL_STD)))
    return seconds * 1000


class HumanTyper:
    """
    A helper class to integrate realistic typing into automation frameworks
    like Playwright, Selenium, or Appium.

    Each framework has its own entry point because their element APIs differ:
      - ``type``               -> Playwright async Locator/ElementHandle
      - ``type_playwright_sync`` -> Playwright sync Locator/ElementHandle
      - ``type_sync``          -> Selenium WebElement
      - ``type_appium``        -> Appium driver (focused element)

    Dwell (keydown->keyup hold) is modelled only on the Playwright paths, where
    ``press(delay=)`` exposes it. Selenium/Appium ``send_keys`` cannot set it.
    """

    def __init__(self, wpm: float = 60.0, layout: str = "qwerty") -> None:
        if not isinstance(wpm, (int, float)) or wpm <= 0:
            raise ValueError("wpm must be a positive number")
        self.wpm = wpm
        self.layout = layout

    async def type(self, page_element: Any, text: str) -> None:
        """
        Type into a Playwright async Locator/ElementHandle with realistic
        timing, errors, corrections, and per-keystroke dwell.

        Example:
            typer = HumanTyper(wpm=70)
            box = page.locator("input[name='search']")
            await box.click()
            await typer.type(box, "Hello world!")
        """
        last_time = 0.0
        for t, action, _ in _typing_history(text, self.wpm, self.layout):
            delay = t - last_time
            if delay > 0:
                await asyncio.sleep(delay)
            last_time = t

            if "BACKSPACE" in action:
                await page_element.press("Backspace", delay=_dwell_ms())
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    await page_element.press(char, delay=_dwell_ms())
            elif "TYPED" in action:  # TYPED, TYPED_ERROR
                await page_element.press(_extract_char(action), delay=_dwell_ms())

    def type_playwright_sync(self, page_element: Any, text: str) -> None:
        """
        Type into a Playwright sync Locator/ElementHandle with realistic
        timing, errors, corrections, and per-keystroke dwell.

        Example:
            typer = HumanTyper(wpm=70)
            box = page.locator("input[name='search']")
            box.click()
            typer.type_playwright_sync(box, "Hello world!")
        """
        last_time = 0.0
        for t, action, _ in _typing_history(text, self.wpm, self.layout):
            delay = t - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = t

            if "BACKSPACE" in action:
                page_element.press("Backspace", delay=_dwell_ms())
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    page_element.press(char, delay=_dwell_ms())
            elif "TYPED" in action:  # TYPED, TYPED_ERROR
                page_element.press(_extract_char(action), delay=_dwell_ms())

    def type_sync(self, selenium_element: Any, text: str) -> None:
        """
        Type into a Selenium WebElement with realistic timing, errors, and
        corrections. No dwell: ``send_keys`` cannot control key hold time.

        Example:
            typer = HumanTyper(wpm=65)
            box = driver.find_element(By.NAME, "search")
            box.click()
            typer.type_sync(box, "Hello Selenium!")
        """
        from selenium.webdriver.common.keys import Keys

        last_time = 0.0
        for t, action, _ in _typing_history(text, self.wpm, self.layout):
            delay = t - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = t

            if "BACKSPACE" in action:
                selenium_element.send_keys(Keys.BACK_SPACE)
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    selenium_element.send_keys(char)
            elif "TYPED" in action:  # TYPED, TYPED_ERROR
                selenium_element.send_keys(_extract_char(action))

    def type_appium(self, driver: Any, text: str) -> None:
        """
        Type into the focused mobile element using W3C Actions. Requires the
        target element to already be focused. No dwell (send_keys-based).

        Example:
            typer = HumanTyper(wpm=45)
            box = driver.find_element(...)
            box.click()  # ensure focus
            typer.type_appium(driver, "Hello Appium")
        """
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys

        last_time = 0.0
        for t, action, _ in _typing_history(text, self.wpm, self.layout):
            delay = t - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = t

            actions = ActionChains(driver)
            if "BACKSPACE" in action:
                actions.send_keys(Keys.BACK_SPACE).perform()
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    actions.send_keys(char)
                actions.perform()
            elif "TYPED" in action:  # TYPED, TYPED_ERROR
                actions.send_keys(_extract_char(action)).perform()
