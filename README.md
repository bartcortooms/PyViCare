# Viessmann API CLI Sensor Lister

This script is a command-line tool to list all available sensors/features for devices connected to your Viessmann heating system via the Viessmann ViCare API. It directly queries the API without using the PyViCare library.

## Prerequisites

- Python 3.x
- `requests` library: Install it using pip:
  ```bash
  pip install requests
  ```

## Usage

1.  **Obtain an API Token:** You need a valid Viessmann API token.
2.  **Run the script:**
    Execute the script from your terminal, providing the API token via the `--token` argument:

    ```bash
    python vicare_cli.py --token YOUR_API_TOKEN_HERE
    ```

    Replace `YOUR_API_TOKEN_HERE` with your actual Viessmann API token.

## How it Works

The script performs the following steps:
1. Takes your API token as input.
2. Discovers your `installationId` and `gatewaySerial` by querying the `/equipment/installations` endpoint.
3. For each gateway, it discovers the `deviceId`(s) by querying the `/equipment/installations/{installationId}/gateways/{gatewaySerial}/devices` endpoint.
4. For each device, it fetches all available features (sensors, data points, commands, etc.) by querying the `/features/installations/{installationId}/gateways/{gatewaySerial}/devices/{deviceId}/features` endpoint.
5. It then prints the details of each feature to the console.

**Note:** The API token is used for authentication with the Viessmann API and should be kept confidential. Do not hardcode it into the script.
