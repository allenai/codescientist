# ModalUtilStopAllApps.py

import os
import time

def list_all_apps():
    # Run the 'modal app list` command, capture the output
    os.system('modal app list > all_running_modal_apps.temp.txt')
    # Open the file and read the lines
    with open('all_running_modal_apps.temp.txt', 'r') as file:
        lines = file.readlines()

    # Split the lines based on the `│` character
    app_names = []
    for line in lines:
        try:
            fields = line.split('│')
            if (len(fields) > 2):
                app_name = fields[2].strip()
                app_names.append(app_name)
        except:
            continue

    return app_names



def main():
    # Get a list of app names
    app_names = list_all_apps()

    print("Found " + str(len(app_names)) + " running Modal apps.")

    # Ask (Y/N) if the user wants to stop all the apps
    response = input("Do you want to stop all these apps? (Y/N): ")
    if (response.lower() == "y"):
        # Stop all the apps
        for app_name in app_names:
            print("Stopping app: " + app_name)
            os.system('modal app stop ' + app_name)
            time.sleep(0.5)
        print("All apps stopped.")
    else:
        print("No apps were stopped.")



if __name__ == '__main__':
    main()