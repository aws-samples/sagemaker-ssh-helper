import json
import logging
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import List

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC  # noqa

from sagemaker_ssh_helper.ide import SSHIDE


class JupyterNotebook:
    def __init__(self, local_path: Path):
        self.local_path = local_path
        with open(self.local_path) as f:
            self.ipynb = json.load(f)

    def save_as(self, local_path: Path):
        with open(local_path, 'w') as f:
            json.dump(self.ipynb, f)

    def insert_code_cell(self, position, code_lines: List[str]):
        self.ipynb['cells'].insert(position, {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': code_lines
        })


class SageMakerStudioAutomation:
    logger = logging.getLogger('sagemaker-ssh-helper:SageMakerStudioAutomation')

    def __init__(self, ide: SSHIDE, browser: webdriver.Remote):
        self.ide = ide
        self.sagemaker_client = ide.client
        self.browser = browser

    def launch_sagemaker_studio(self):
        studio_pre_signed_url_response = self.sagemaker_client.create_presigned_domain_url(
            DomainId=self.ide.domain_id,
            UserProfileName=self.ide.user,
        )
        studio_pre_signed_url = studio_pre_signed_url_response['AuthorizedUrl']

        self.logger.info("Launching SageMaker Studio")
        self.browser.get(studio_pre_signed_url)

        self.wait_studio_launch()

    def wait_studio_launch(self):
        self.logger.info("Waiting for SageMaker Studio UI to load.")
        start_time = time.time()
        try:
            WebDriverWait(self.browser, timedelta(minutes=30).total_seconds()).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='space-menu']"))
            )
            self.logger.info(
                "SageMaker Studio UI is loaded. Time to load: %s seconds",
                int(time.time() - start_time)
            )
        except TimeoutException as e:
            self.logger.error(
                "Time out waiting for SageMaker Studio UI to load. Elapsed time: %s seconds",
                int(time.time() - start_time)
            )
            raise e

        self.logger.info("Waiting for possible dialogs to appear and closing them")
        time.sleep(10)
        ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()
        ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()

        self.close_all_tabs()

        space_menu_item = self.browser.find_element(By.XPATH, "//div[@id='space-menu']")
        self.logger.info(f"Found SageMaker Studio space menu item: {space_menu_item.text}")
        assert space_menu_item.text == f'{self.ide.user} / Personal Studio'

    def close_sagemaker_studio(self):
        self.logger.info("Closing SageMaker Studio")
        self.browser.close()

    def close_all_tabs(self):
        self._click_file_menu()
        time.sleep(2)
        self._click_close_all_tabs()

    def upload_file_with_overwrite(self, local_file: Path):
        self.logger.info("File upload started.")
        file_drop_area = self.browser.find_element(
            By.XPATH,
            "//ul[@class='jp-DirListing-content']"
        )
        self.logger.info(f"Found file browser to drop the file to: {file_drop_area.text}")
        time.sleep(2)
        file_input = self.browser.execute_script(
            Path(os.path.dirname(__file__), 'js/drop_studio_file.js').read_text(),
            file_drop_area, 0, 0
        )
        self.logger.info(f"Created a file upload item: {file_input}")
        file_input.send_keys(str(local_file.absolute()))
        time.sleep(2)  # Give time to overwrite dialog to apper
        self._confirm_overwrite()
        self.logger.info("File upload finished: %s", local_file)

    def open_file_from_path(self, jupyter_path: str, instance_type_if_needed: str):
        self._click_file_menu()
        time.sleep(2)
        self._click_open_from_path()
        self._send_path_to_open_dialog(jupyter_path)
        self._click_dialog_open()
        time.sleep(5)  # Wait for possible Environment Select dialog to appear
        self._select_instance_type_if_asked(instance_type_if_needed)

        kernel_name = self._wait_and_get_notebook_kernel_name()

        # TODO: make it possible to choose different kernel
        if "Data Science 2.0" not in kernel_name or "Python 3" not in kernel_name:
            raise ValueError(f"Unexpected kernel name: {kernel_name}")

        time.sleep(10)  # Give time for UI to update and Restart button to appear

    def restart_kernel_and_run_all_cells(self):
        self._click_kernel_menu()
        time.sleep(2)  # wait for menu to pop-up
        self._click_kernel_restart_and_run_all_cells()
        time.sleep(10)  # wait for dialog to pop-up
        self._confirm_restart()
        time.sleep(15)  # Give time to restart

    def download_current_file(self):
        self._click_file_menu()
        time.sleep(2)
        self._click_download()
        time.sleep(2)

    def save_current_file(self):
        self.logger.info("Closing possible dialogs (e.g. lost connection)")
        ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()
        ActionChains(self.browser).send_keys(Keys.ESCAPE).perform()
        time.sleep(2)
        self._click_file_menu()
        time.sleep(2)
        self._click_save()
        time.sleep(2)

    def _click_file_menu(self):
        file_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-MenuBar-itemLabel p-MenuBar-itemLabel' "
            "and text()='File']"
        )
        self.logger.info(f"Found file menu item: {file_menu_item.text}")
        file_menu_item.click()

    def _click_close_all_tabs(self):
        self.logger.info("Closing all tabs")
        close_all_tabs_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
            "and text()='Close All Tabs']")
        self.logger.info(f"Found close all tabs menu item: {close_all_tabs_item.text}")
        close_all_tabs_item.click()

    def _confirm_overwrite(self):
        overwrite_button = self.browser.find_elements(
            By.XPATH,
            "//div[@class='jp-Dialog-buttonLabel' "
            "and text()='Overwrite']"
        )
        if len(overwrite_button) > 0:
            self.logger.info(f"Found overwrite dialog button: {overwrite_button[0].text}")
            overwrite_button[0].click()

    def _click_open_from_path(self):
        self.logger.info("Opening file from Path")
        open_from_path_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
            "and text()='Open from Path…']")
        self.logger.info(f"Found open from path menu item: {open_from_path_menu_item.text}")
        open_from_path_menu_item.click()

    def _send_path_to_open_dialog(self, path):
        open_input_text = self.browser.find_element(
            By.XPATH,
            "//input[@id='jp-dialog-input-id']"
        )
        self.logger.info(f"Found open dialog input text: {open_input_text.text}")
        open_input_text.send_keys(path)

    def _click_dialog_open(self):
        open_button = self.browser.find_element(
            By.XPATH,
            "//div[@class='jp-Dialog-buttonLabel' "
            "and text()='Open']"
        )
        self.logger.info(f"Found open dialog button: {open_button.text}")
        open_button.click()

    def _select_instance_type_if_asked(self, instance_type):
        self.logger.info(f"Checking for environment select dialog")
        # noinspection SpellCheckingInspection
        instance_select_input = self.browser.find_elements(
            By.XPATH,
            "//input[@class='qa-SagemakerNotebookExtensionKernelDialogInstnaceSelect jp-mod-styled']"
        )
        if len(instance_select_input) > 0:
            hidden_input = instance_select_input[0]
            self.logger.info(f"Found instance select hidden item: {hidden_input.text}")
            self.browser.execute_script("arguments[0].setAttribute('value', '" + instance_type + "')", hidden_input)
            self._click_dialog_select()
        else:
            self.logger.info(f"Environment select dialog not found")

    def _click_dialog_select(self):
        select_button = self.browser.find_element(
            By.XPATH,
            "//div[@class='jp-Dialog-buttonLabel' "
            "and text()='Select']"
        )
        self.logger.info(f"Found select dialog button: {select_button.text}")
        select_button.click()

    def _wait_and_get_notebook_kernel_name(self):
        self.logger.info("Waiting for the kernel name")
        WebDriverWait(self.browser, 300).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//button[@class='bp3-button bp3-minimal jp-Toolbar-kernelName "
                "jp-ToolbarButtonComponent minimal jp-Button']/span/span[not(text()='No Kernel')]"
            ))
        )
        self.logger.info("Fetching the kernel name")
        kernel_item = self.browser.find_element(
            By.XPATH,
            "//button[@class='bp3-button bp3-minimal jp-Toolbar-kernelName "
            "jp-ToolbarButtonComponent minimal jp-Button']"
        )
        self.logger.info(f"Found Kernel name: {kernel_item.text}")
        kernel_name = kernel_item.text
        return kernel_name

    def _click_kernel_menu(self):
        kernel_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-MenuBar-itemLabel p-MenuBar-itemLabel' "
            "and text()='Kernel']"
        )
        self.logger.info(f"Found kernel menu item: {kernel_menu_item.text}")
        kernel_menu_item.click()

    def _click_kernel_restart_and_run_all_cells(self):
        self.logger.info("Restarting kernel and running all cells")
        restart_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
            "and text()='Restart Kernel and Run All Cells…']")
        self.logger.info(f"Found restart kernel menu item: {restart_menu_item.text}")
        restart_menu_item.click()

    def _confirm_restart(self):
        restart_button = self.browser.find_element(
            By.XPATH,
            "//div[@class='jp-Dialog-buttonLabel' "
            "and text()='Restart']"
        )
        self.logger.info(f"Found restart button: {restart_button.text}")
        restart_button.click()

    def _click_download(self):
        self.logger.info("Downloading file")
        download_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
            "and text()='Download']")
        self.logger.info(f"Found download menu item: {download_menu_item.text}")
        download_menu_item.click()

    def _click_save(self):
        self.logger.info("Saving file")
        save_menu_item = self.browser.find_element(
            By.XPATH,
            "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
            "and text()='Save Notebook']")
        self.logger.info(f"Found save menu item: {save_menu_item.text}")
        save_menu_item.click()
