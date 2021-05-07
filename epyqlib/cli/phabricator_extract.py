import base64
import click
import datetime
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from urllib.parse import urljoin

# The output:
# file_dump: Dump of all of the Phabricator files in the system
# maniphest_dump: Text dump of the Phabricator tasks/tickets in the system
# pdf_dump: PDF representations of the Phabricator tasks
# file_search.txt: Searchable text that provides link between
#   Phabricator maniphest tickets/tasks and the files in file_dump


def extract_files_search(phabricator_url, api_token):
    # Retrieve the files data from Phabricator.
    file_search_request_data = {
        "api.token": api_token,
        "after": None,
    }

    file_search_result_data = []
    while True:
        file_search_url = urljoin(phabricator_url, "/api/file.search")
        response = requests.post(
            file_search_url, data=file_search_request_data, verify=False
        )
        json_response = response.json()
        result_data = json_response["result"]["data"]
        file_search_result_data.extend(result_data)
        result_cursor = json_response["result"]["cursor"]
        next_after = result_cursor["after"]
        next_before = result_cursor["before"]
        if next_after is None:
            # This is a special case that was necessary in order to skip over restricted files.
            # See the files in the comments at the bottom of this file.
            if next_before == "23067":
                next_after = 22840
            else:
                break
        file_search_request_data["after"] = next_after

    return file_search_result_data


def generate_file_search_text_file(target, file_search_result_data):
    # Generate the file_search.txt file, which provides a link between the Maniphest tickets and the files.
    file_name_out = os.path.join(target, "file_search.txt")
    with open(file_name_out, "w", encoding="utf-8") as file_to_save:
        for result in file_search_result_data:
            file_to_save.write(f"id: {result['id']}\n")
            file_to_save.write(f"phid: {result['phid']}\n")
            file_to_save.write(f"uri: {result['fields']['uri']}\n")
            file_to_save.write(f"name: {result['fields']['name']}\n")
            file_to_save.write(f"type: {result['type']}\n\n")


def download_files(phabricator_url, api_token, target, file_search_result_data):
    # File download from Phabricator given file search results.
    file_download_request_data = {
        "api.token": api_token,
        "phid": None,
    }

    file_output_dir = os.path.join(target, "file_dump")
    for result_data in file_search_result_data:
        id = result_data["id"]
        file_name = result_data["fields"]["name"]
        if file_name is None or file_name == "":
            file_name = "BLANK_FILE_NAME"
        file_name_out = os.path.join(file_output_dir, str(id), file_name)
        os.makedirs(os.path.dirname(file_name_out), exist_ok=True)
        file_download_request_data["phid"] = result_data["phid"]
        print(f"File download: {id} {file_name}")
        file_download_url = urljoin(phabricator_url, "/api/file.download")
        response = requests.post(
            file_download_url, data=file_download_request_data, verify=False
        )
        file_data = response.json()["result"]
        if file_data is not None:
            data_bytes = file_data.encode("utf-8")
        else:
            print("WARNING: DATA IS NONE")
            data_bytes = "".encode("utf-8")
            readme_file_name_out = os.path.join(
                file_output_dir, str(id), "readme_phabricator_extract.txt"
            )
            with open(readme_file_name_out, "w") as readme_file_to_save:
                readme_file_to_save.write(f"id: {id}\n")
                readme_file_to_save.write(f"file name: {file_name}\n")
                readme_file_to_save.write(f"phid: {result_data['phid']}\n")
                readme_file_to_save.write(
                    "NOTE: This file was written because the contents of the file were either empty or unable to be read."
                )
        with open(file_name_out, "wb") as file_to_save:
            decoded_data = base64.decodebytes(data_bytes)
            file_to_save.write(decoded_data)


def extract_file_data(phabricator_url, api_token, target):
    # Extract files from Phabricator and store in target directory.
    file_search_result_data = extract_files_search(phabricator_url, api_token)
    generate_file_search_text_file(target, file_search_result_data)
    download_files(phabricator_url, api_token, target, file_search_result_data)


def get_users(phabricator_url, api_token):
    # Retrieve user information from Phabricator.
    user_search_request_data = {
        "api.token": api_token,
        "after": None,
    }

    total_result_data = []
    user_search_url = urljoin(phabricator_url, "/api/user.search")

    while True:
        response = requests.post(
            user_search_url, data=user_search_request_data, verify=False
        )
        json_response = response.json()
        result_data = json_response["result"]["data"]
        total_result_data.extend(result_data)
        result_cursor = json_response["result"]["cursor"]
        next_after = result_cursor["after"]
        if next_after is None:
            break
        user_search_request_data["after"] = next_after

    user_dict = {}
    for result_data in total_result_data:
        user_phid = result_data["phid"]
        user_name = result_data["fields"]["realName"]
        user_dict[user_phid] = user_name

    return user_dict


def extract_maniphest_search(phabricator_url, api_token):
    # Retrieve Maniphest ticket/task information.
    maniphest_search_request_data = {
        "api.token": api_token,
        "after": None,
    }

    maniphest_search_result_data = []
    maniphest_search_url = urljoin(phabricator_url, "/api/maniphest.search")

    while True:
        response = requests.post(
            maniphest_search_url, data=maniphest_search_request_data, verify=False
        )
        json_response = response.json()
        result_data = json_response["result"]["data"]
        maniphest_search_result_data.extend(result_data)
        result_cursor = json_response["result"]["cursor"]
        next_after = result_cursor["after"]
        if next_after is None:
            break
        maniphest_search_request_data["after"] = next_after

    return maniphest_search_result_data


def write_maniphest_data_to_text_file(target, maniphest_search_result_data, user_dict):
    # Write Maniphest ticket/task information to searchable text file.
    file_output_dir = os.path.join(target, "maniphest_dump")
    os.makedirs(file_output_dir, exist_ok=True)
    maniphest_id_list = []
    for result_data in maniphest_search_result_data:
        maniphest_id = result_data["id"]
        maniphest_id_list.append(maniphest_id)

        maniphest_file_name = os.path.join(file_output_dir, str(maniphest_id) + ".txt")
        with open(maniphest_file_name, "w", encoding="utf-8") as maniphest_fp:
            maniphest_fp.write(f"name: {result_data['fields']['name']}\n")
            maniphest_fp.write(f"status: {result_data['fields']['status']['name']}\n")
            maniphest_fp.write(
                f"priority: {result_data['fields']['priority']['name']}\n"
            )
            maniphest_fp.write(
                f"date created: {datetime.datetime.fromtimestamp(result_data['fields']['dateCreated'])}\n"
            )
            maniphest_fp.write(
                f"date modified: {datetime.datetime.fromtimestamp(result_data['fields']['dateModified'])}\n"
            )
            maniphest_fp.write(
                f"author: {user_dict.get(result_data['fields']['authorPHID'])}\n"
            )
            maniphest_fp.write(
                f"owner: {user_dict.get(result_data['fields']['ownerPHID'])}\n"
            )
            maniphest_fp.write(
                f"description: {result_data['fields']['description']['raw']}\n"
            )
            if len(result_data["attachments"]) > 0:
                maniphest_fp.write(f"attachments: {result_data['attachments']}\n")


def maniphest_to_pdf(
    maniphest_search_result_data,
    target,
    chromedriver,
    phabricator_url,
    username,
    password,
):
    # PDF dump of Maniphest ticket/task web pages.
    file_output_dir = os.path.join(target, "pdf_dump")

    options = webdriver.ChromeOptions()

    settings = {
        "recentDestinations": [
            {
                "id": "Save as PDF",
                "origin": "local",
                "account": "",
            }
        ],
        "selectedDestinationId": "Save as PDF",
        "version": 2,
    }
    # TODO: Never could get command to save in the specified directory. Always saves to Downloads dir.
    prefs = {
        "profile.default_content_settings.popups": 0,
        "download.default_directory": file_output_dir + os.path.sep,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "printing.print_preview_sticky_settings.appState": json.dumps(settings),
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--kiosk-printing")

    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--ignore-certificate-errors")
    # TODO: automatically load/install chromedriver
    driver = webdriver.Chrome(executable_path=chromedriver, options=options)
    driver.get(phabricator_url)

    elem = driver.find_element_by_name("username")
    elem.clear()
    elem.send_keys(username)

    elem = driver.find_element_by_name("password")
    elem.clear()
    elem.send_keys(password)

    elem.send_keys(Keys.RETURN)

    os.makedirs(file_output_dir, exist_ok=True)
    for result_data in maniphest_search_result_data:
        maniphest_id = result_data["id"]
        maniphest_url = urljoin(phabricator_url, "/T" + str(maniphest_id))
        driver.get(maniphest_url)
        # TODO: Never could get command to save in the specified directory. Always saves to Downloads dir.
        driver.execute_script(f"window.print();")

    driver.close()


def extract_tickets(
    chromedriver, phabricator_url, api_token, target, username, password
):
    user_dict = get_users(phabricator_url, api_token)
    maniphest_search_result_data = extract_maniphest_search(phabricator_url, api_token)
    write_maniphest_data_to_text_file(target, maniphest_search_result_data, user_dict)
    maniphest_to_pdf(
        maniphest_search_result_data,
        target,
        chromedriver,
        phabricator_url,
        username,
        password,
    )


def create_command():
    @click.command()
    @click.option(
        "--target",
        help="path to the output directory",
        type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
        required=True,
    )
    @click.option(
        "--chromedriver",
        help="path to chromedriver",
        type=click.Path(exists=True, file_okay=True, resolve_path=True),
        required=True,
    )
    @click.option(
        "--phabricator-url",
        help="The base URL for the Phabricator server.",
        type=str,
        required=True,
    )
    @click.option(
        "--api-token",
        help="""
            Your Phabricator API token.
            These are managed under your user settings then 'Conduit API Tokens'.
        """,
        type=str,
        required=True,
    )
    @click.option(
        "--username",
        help="Your Phabricator user name.",
        type=str,
        required=True,
    )
    @click.password_option()
    def cli(target, chromedriver, phabricator_url, api_token, username, password):
        extract_file_data(phabricator_url, api_token, target)
        extract_tickets(
            chromedriver, phabricator_url, api_token, target, username, password
        )

    return cli
