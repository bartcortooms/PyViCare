"""
Viessmann ViCare API CLI - Device Feature Lister

This script fetches and displays all available features (sensors, data points, commands, etc.)
for devices connected to a Viessmann heating system using the Viessmann ViCare API.
It directly queries the API without relying on the PyViCare library.

Prerequisites:
- Python 3.x
- `requests` library: Install it using pip:
  pip install requests

Usage:
python vicare_cli.py --token YOUR_API_TOKEN

Replace YOUR_API_TOKEN with your actual Viessmann API token.
The token is required to authenticate with the API.
"""
import argparse
import requests
import json
import sys

VICARE_API_BASE_URL = "https://api.viessmann.com/iot/v2"

def get_installations_and_gateways(api_token):
    """Fetches installations and gateways and extracts (installation_id, gateway_serial) pairs."""
    url = f"{VICARE_API_BASE_URL}/equipment/installations?includeGateways=true"
    headers = {"Authorization": f"Bearer {api_token}"}
    # Errors will be caught by the main try-except block
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    installations_info = []
    if 'data' in data and isinstance(data['data'], list):
        for installation in data['data']:
            if 'id' in installation and 'gateways' in installation and isinstance(installation['gateways'], list):
                installation_id = installation['id']
                for gateway in installation['gateways']:
                    if 'serial' in gateway:
                        installations_info.append((str(installation_id), gateway['serial']))
                    else:
                        print("Warning: Gateway found without a serial number.", file=sys.stderr)
            else:
                print("Warning: Installation found with missing 'id' or 'gateways' information.", file=sys.stderr)
    else:
        print("Warning: 'data' key missing or not a list in installations response.", file=sys.stderr)

    if not installations_info:
        print("Info: No installations and gateways found or error in parsing response.", file=sys.stderr)
    return installations_info

def get_devices(api_token, installation_id, gateway_serial):
    """Fetches device IDs for a given installation and gateway."""
    url = f"{VICARE_API_BASE_URL}/equipment/installations/{installation_id}/gateways/{gateway_serial}/devices?includeFeatures=false"
    headers = {"Authorization": f"Bearer {api_token}"}
    # Errors will be caught by the main try-except block
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    device_ids = []
    if 'data' in data and isinstance(data['data'], list):
        for device in data['data']:
            if 'id' in device:
                device_ids.append(device['id'])
            else:
                print(f"Warning: Device found without an ID in gateway {gateway_serial}.", file=sys.stderr)
    else:
        print(f"Warning: 'data' key missing or not a list in devices response for gateway {gateway_serial}.", file=sys.stderr)

    if not device_ids:
        print(f"Info: No devices found for installation {installation_id}, gateway {gateway_serial}.", file=sys.stderr)
    return device_ids

def get_all_features(api_token, installation_id, gateway_serial, device_id):
    """Fetches all features for a given device."""
    url = f"{VICARE_API_BASE_URL}/features/installations/{installation_id}/gateways/{gateway_serial}/devices/{device_id}/features"
    headers = {"Authorization": f"Bearer {api_token}"}
    # Errors will be caught by the main try-except block
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data

def main():
    parser = argparse.ArgumentParser(
        description="Viessmann ViCare API CLI - Device Feature Lister. Fetches and displays device features.",
        epilog="Example: python vicare_cli.py --token YOUR_API_TOKEN_HERE"
    )
    parser.add_argument(
        "--token",
        "-t",
        type=str,
        required=True,
        help="Viessmann API token",
    )
    args = parser.parse_args()

    print(f"Using Token: {args.token[:5]}...{args.token[-5:]}")

    try:
        installations = get_installations_and_gateways(args.token)
        if not installations:
            print("No installations found. This could be due to an incorrect token, no installations associated with the account, or an API issue.", file=sys.stderr)
            return

        for installation_id, gateway_serial in installations:
            print(f"\nInstallation ID: {installation_id}, Gateway Serial: {gateway_serial}")
            device_ids = get_devices(args.token, installation_id, gateway_serial)

            if not device_ids:
                continue

            print(f"  Device IDs: {device_ids}")
            for device_id in device_ids:
                print(f"    --- Features for Device ID: {device_id} ---")
                features_response = get_all_features(args.token, installation_id, gateway_serial, device_id)

                if features_response and 'data' in features_response and isinstance(features_response['data'], list):
                    features_list = features_response['data']
                    if not features_list:
                        print(f"      Info: No features found for device {device_id}.")
                        continue

                    for feature_idx, feature in enumerate(features_list):
                        try:
                            print(f"      Feature [{feature_idx + 1}]")
                            print(f"        Name: {feature.get('feature', 'N/A')}")
                            print(f"        URI: {feature.get('uri', 'N/A')}")
                            print(f"        Data Type: {feature.get('dataType', 'N/A')}")

                            if 'properties' in feature:
                                print(f"        Properties: {json.dumps(feature['properties'], indent=2).replace(chr(10), chr(10) + '          ')}")

                            if 'commands' in feature:
                                print(f"        Commands: {json.dumps(feature['commands'], indent=2).replace(chr(10), chr(10) + '          ')}")

                            if 'components' in feature:
                                print(f"        Components: {json.dumps(feature['components'], indent=2).replace(chr(10), chr(10) + '          ')}")

                            if feature_idx < len(features_list) - 1:
                                print("      ---")
                        except KeyError as e:
                            print(f"      Warning: Key {e} not found in feature. Skipping this detail.", file=sys.stderr)
                        except Exception as e:
                            print(f"      An unexpected error occurred while processing a feature: {e}", file=sys.stderr)
                elif features_response:
                     print(f"      Features data for {device_id} (unexpected format):", file=sys.stderr)
                     print(json.dumps(features_response, indent=2), file=sys.stderr)
                else:
                    print(f"      Could not retrieve features for device {device_id}.", file=sys.stderr)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.reason}", file=sys.stderr)
        if e.response.text:
            try:
                error_data = e.response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}", file=sys.stderr)
            except json.JSONDecodeError:
                print(f"Error details (raw): {e.response.text}", file=sys.stderr)
        print("Please check your API token, network connection, and the API documentation.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: An error occurred connecting to the Viessmann API: {e}", file=sys.stderr)
        print("Please check your network connection.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: Failed to parse API response: {e}", file=sys.stderr)
        print("The API might be temporarily unavailable or returned an unexpected response.", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"Data Processing Error: Missing expected key '{e}' in API response.", file=sys.stderr)
        print("The API response structure might have changed. Please report this issue.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
