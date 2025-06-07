"""
Viessmann Cooling Mode Check CLI using PyViCare with Direct API Token.

This script checks if any connected Viessmann heating devices are currently
in a cooling mode. It uses PyViCare to interact with the Viessmann API,
authenticating with a directly provided API token.

Prerequisites:
- Python 3.x
- PyViCare library: pip install PyViCare
- Dependencies for PyViCare (e.g., requests, authlib)
- Environment variables / Command-line arguments:
    - VICARE_API_TOKEN (or --api-token): Your Viessmann API access token. (Required)
    - VICARE_CLIENT_ID (or --client-id): (Optional) Your Viessmann API client ID.
                                       Defaults to PyViCare's standard client ID if not set
                                       ('1c681a9cfa03a0fe940f4fcfU6caCd8').
    - VICARE_DEBUG_LIB: (Optional) Set to 'true' to enable verbose logging
                        from PyViCare and underlying libraries. Defaults to 'false'.

Usage:
    python check_cooling_mode_cli.py --api-token YOUR_TOKEN_HERE [--client-id YOUR_CLIENT_ID_HERE]
Or (using environment variables):
    export VICARE_API_TOKEN="YOUR_TOKEN_HERE"
    export VICARE_CLIENT_ID="YOUR_CLIENT_ID_HERE" # Optional, defaults if not set
    python check_cooling_mode_cli.py
"""
import os
import sys
import logging
import argparse
import requests
from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError, PyViCareRateLimitError
from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
from authlib.integrations.requests_client import OAuth2Session


# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('vicare_cooling_check')

# Define known cooling modes and programs
KNOWN_COOLING_MODES = [
    "cooling", "comfortCooling", "forcedCooling", "ecoCooling",
    "COOLING", "COMFORT_COOLING", "FORCED_COOLING", "ECO_COOLING",
    "activeCooling", "permanentCooling"
]
KNOWN_COOLING_PROGRAMS = [
    "comfortCooling", "comfortCoolingEnergySaving",
    "normalCooling", "normalCoolingEnergySaving",
    "reducedCooling", "reducedCoolingEnergySaving",
    "ecoCooling", "cooling"
]

class TokenAuthOAuthManager(AbstractViCareOAuthManager):
    def __init__(self, raw_api_token: str, client_id: str):
        """
        OAuthManager that uses a pre-existing raw API token.
        Token renewal is not supported with this manager.
        """
        if not raw_api_token:
            raise ValueError("API token cannot be empty.")
        if not client_id:
            raise ValueError("Client ID cannot be empty for OAuth2Session.")

        token_dict = {
            'access_token': raw_api_token,
            'token_type': 'Bearer',
        }

        oauth_session = OAuth2Session(client_id=client_id, token=token_dict)

        super().__init__(oauth_session)
        logger.info("Initialized TokenAuthOAuthManager with provided API token.")

    def renewToken(self) -> None:
        """
        Token renewal is not supported when using a static API token.
        """
        logger.error("Static API token has expired or is invalid. Token renewal is not supported in this mode.")
        raise RuntimeError("API token expired and renewal is not supported with static token authentication.")


def initialize_vicare(api_token_str: str, client_id_str: str):
    logger.info("Initializing PyViCare with API Token...")

    if not api_token_str: # Should be caught by argparse, but as a safeguard
        logger.error("API Token (from --api-token or VICARE_API_TOKEN) must be provided.")
        sys.exit(1)

    # Use provided client_id_str or default if it's empty or None.
    # The default for --client-id in argparse is already the PyViCare default,
    # so client_id_str here should always have a value.
    final_client_id = client_id_str
    if not client_id_str: # Should not happen if argparse default is set correctly
        logger.warning(f"Client ID was empty, using PyViCare default: 1c681a9cfa03a0fe940f4fcfU6caCd8")
        final_client_id = '1c681a9cfa03a0fe940f4fcfU6caCd8'


    try:
        logger.info(f"Using Client ID: {final_client_id}")
        logger.info(f"Using API Token: {api_token_str[:5]}...{api_token_str[-5:]}") # Mask token

        # 1. Instantiate the custom OAuth manager
        token_oauth_manager = TokenAuthOAuthManager(raw_api_token=api_token_str, client_id=final_client_id)

        # 2. Instantiate PyViCare (no arguments in constructor)
        vicare = PyViCare()

        # 3. Initialize PyViCare with the custom OAuth manager
        vicare.initWithExternalOAuth(oauth_manager=token_oauth_manager)

        # 4. Optionally set cache duration (if desired)
        # vicare.setCacheDuration(60) # Default is 0 (no cache), or 60 if you use initWithCredentials
                                     # For direct token, caching might be less critical or handled differently.
                                     # Let's keep it commented out for now unless deemed necessary.

        logger.info("Successfully initialized PyViCare with token-based authentication using initWithExternalOAuth.")
        return vicare
    except Exception as e:
        logger.error(f"Error during PyViCare initialization with API token: {e}", exc_info=True)
        sys.exit(1)


def discover_devices(vicare_instance):
    """
    Discovers and creates full Device objects from the PyViCare instance.
    """
    if not vicare_instance or not hasattr(vicare_instance, 'devices') or not vicare_instance.devices:
        logger.warning("No devices found in PyViCare instance or instance is not valid.")
        return []

    logger.info(f"Found {len(vicare_instance.devices)} device configuration(s) in the installation.")

    all_devices = []
    for device_config in vicare_instance.devices:
        try:
            logger.info(f"Processing PyViCareDeviceConfig: device_id {device_config.device_id}, model_id: {device_config.model_id}, status: {device_config.status}")
            device = device_config.service
            logger.info(f"Successfully created Device object: {device.getModel()} (Type: {type(device).__name__}), from device_id: {device_config.device_id}")
            all_devices.append(device)
        except PyViCareRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Error creating full Device object from PyViCareDeviceConfig (device_id: {device_config.device_id}, model_id: {device_config.model_id}): {e}", exc_info=True)

    return all_devices

def check_devices_for_cooling(devices_list):
    """
    Checks each device and its circuits for active cooling modes or programs.
    """
    cooling_devices_found = []
    if not devices_list:
        logger.info("No devices to check for cooling mode.")
        return cooling_devices_found

    normalized_known_cooling_modes = [m.lower() for m in KNOWN_COOLING_MODES]
    normalized_known_cooling_programs = [p.lower() for p in KNOWN_COOLING_PROGRAMS]

    for device in devices_list:
        logger.info(f"Checking device: {device.getModel()} (Type: {type(device).__name__})")
        try:
            if not hasattr(device, 'circuits') or not device.circuits:
                logger.info(f"  Device {device.getModel()} has no circuits to check or 'circuits' attribute is missing.")
                continue

            for i, circuit in enumerate(device.circuits):
                circuit_name = f"Circuit {i}"
                try:
                    if hasattr(circuit, 'component_name') and circuit.component_name:
                         circuit_name = f"{circuit.component_name} (Circuit {i})"
                except Exception:
                    pass

                logger.info(f"  Checking {circuit_name} of {device.getModel()}...")
                cooling_detected_for_circuit = False

                try:
                    active_mode = circuit.getActiveMode()
                    logger.info(f"    Active mode for {circuit_name}: '{active_mode}'")
                    if active_mode and active_mode.lower() in normalized_known_cooling_modes:
                        logger.warning(f"    COOLING DETECTED for {device.getModel()} [{circuit_name}] via active mode: {active_mode}")
                        cooling_devices_found.append({
                            "device_model": device.getModel(),
                            "device_type": type(device).__name__,
                            "circuit": circuit_name,
                            "detected_by": "active_mode",
                            "value": active_mode
                        })
                        cooling_detected_for_circuit = True
                except PyViCareNotSupportedFeatureError:
                    logger.info(f"    Active mode feature not supported for {circuit_name} on {device.getModel()}.")
                except PyViCareRateLimitError: raise
                except Exception as e:
                    logger.error(f"    Error getting active mode for {circuit_name} on {device.getModel()}: {e}", exc_info=True)

                if not cooling_detected_for_circuit:
                    try:
                        active_program = circuit.getActiveProgram()
                        logger.info(f"    Active program for {circuit_name}: '{active_program}'")
                        if active_program and active_program.lower() in normalized_known_cooling_programs:
                            logger.warning(f"    COOLING DETECTED for {device.getModel()} [{circuit_name}] via active program: {active_program}")
                            cooling_devices_found.append({
                                "device_model": device.getModel(),
                                "device_type": type(device).__name__,
                                "circuit": circuit_name,
                                "detected_by": "active_program",
                                "value": active_program
                            })
                    except PyViCareNotSupportedFeatureError:
                        logger.info(f"    Active program feature not supported for {circuit_name} on {device.getModel()}.")
                    except PyViCareRateLimitError: raise
                    except Exception as e:
                        logger.error(f"    Error getting active program for {circuit_name} on {device.getModel()}: {e}", exc_info=True)

        except PyViCareNotSupportedFeatureError:
            logger.info(f"  Device {device.getModel()} does not support circuits or related features needed for cooling check at device level.")
        except AttributeError as e:
             logger.info(f"  Device {device.getModel()} appears to be missing the 'circuits' attribute: {e}")
        except PyViCareRateLimitError: raise
        except Exception as e:
            logger.error(f"  An error occurred while processing device {device.getModel()}: {e}", exc_info=True)

    return cooling_devices_found

def main():
    """
    Main execution function for the Viessmann Cooling Mode Check CLI.
    """
    parser = argparse.ArgumentParser(
        description="Check Viessmann devices for cooling mode using PyViCare and a direct API token.",
        epilog="""
Prerequisites:
- Python 3.x, PyViCare library (pip install PyViCare)
- Environment variables / Command-line arguments:
    - VICARE_API_TOKEN (or --api-token): Your Viessmann API access token. (Required)
    - VICARE_CLIENT_ID (or --client-id): (Optional) Your Viessmann API client ID.
                                       Defaults to PyViCare's standard client ID.
    - VICARE_DEBUG_LIB: (Optional) Set to 'true' for verbose PyViCare logs.
""",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--api-token",
        type=str,
        default=os.getenv('VICARE_API_TOKEN'),
        # required=os.getenv('VICARE_API_TOKEN') is None, # Logic for this is handled explicitly below
        help="Viessmann API Token. Can also be set via VICARE_API_TOKEN environment variable."
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=os.getenv('VICARE_CLIENT_ID', '1c681a9cfa03a0fe940f4fcfU6caCd8'),
        help="Viessmann API Client ID. Can also be set via VICARE_CLIENT_ID. "
             "Defaults to PyViCare standard ID ('1c681a9cfa03a0fe940f4fcfU6caCd8')."
    )
    args = parser.parse_args()

    if not args.api_token:
        logger.error("--api-token (or VICARE_API_TOKEN environment variable) is required.")
        parser.print_help()
        sys.exit(1)

    logger.info("Starting Viessmann Cooling Mode Check CLI (Token Auth)...")

    debug_vicare_library = os.getenv('VICARE_DEBUG_LIB', 'False').lower() == 'true'
    if not debug_vicare_library:
        logger.info("Suppressing verbose PyViCare library logs. Set VICARE_DEBUG_LIB=true to enable.")
        logging.getLogger("PyViCare").setLevel(logging.WARNING)
        logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
        logging.getLogger("oauthlib").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    vicare_instance = None
    try:
        vicare_instance = initialize_vicare(args.api_token, args.client_id)

        logger.info("PyViCare instance created. Discovering devices...")
        devices = discover_devices(vicare_instance)

        if devices:
            logger.info(f"Successfully discovered {len(devices)} device object(s).")
            logger.info("Checking for cooling mode...")
            cooling_info = check_devices_for_cooling(devices)

            if cooling_info:
                logger.warning("--- COOLING MODE DETECTED ---")
                print("""
--- COOLING MODE DETECTED ---""")
                for info in cooling_info:
                    message_stdout = f"""  Device: {info['device_model']} (Type: {info['device_type']})
  Circuit: {info['circuit']}
  Detected By: {info['detected_by']}
  Value: '{info['value']}'
  ----------------------------"""
                    print(message_stdout)
                    logger.warning(message_stdout.replace("\n", " | "))
                print("\n")
            else:
                logger.info("--- NO COOLING MODE DETECTED ---")
                print("""
--- NO COOLING MODE DETECTED ---""")
                print("  No devices or circuits were found to be actively in a cooling mode.\n")

        else:
            logger.warning("No devices were successfully processed or found in the installation.")
            print("""
No Viessmann devices were found or processed.
Ensure your installation is accessible and the API token is correct.
""")

    except PyViCareRateLimitError as e:
        logger.error(f"Viessmann API rate limit was hit: {e}", exc_info=True)
        print(f"\nERROR: Viessmann API rate limit was hit. Please try again later. Details: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        logger.error(f"A connection error occurred: {e}", exc_info=True)
        print(f"\nERROR: A network connection error occurred. Please check your internet connection. Details: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected critical error occurred: {e}", exc_info=True)
        print(f"\nAn unexpected critical error occurred: {e}")
        sys.exit(1)
    finally:
        logger.info("Cooling mode check finished.")

if __name__ == "__main__":
    main()
