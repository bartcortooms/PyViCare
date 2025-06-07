"""
Viessmann Cooling Mode Check CLI using PyViCare.

This script checks if any connected Viessmann heating devices are currently
in a cooling mode. It uses PyViCare to interact with the Viessmann API.

Prerequisites:
- Python 3.x
- PyViCare library: pip install PyViCare
- Environment variables for authentication:
    - VICARE_EMAIL: Your Viessmann account email.
    - VICARE_PASSWORD: Your Viessmann account password.
    - VICARE_CLIENT_ID: (Optional) Your Viessmann API client ID.
                       Defaults to PyViCare's standard client ID if not set.
                       The default is usually: '1c681a9cfa03a0fe940f4fcfU6caCd8'
    - VICARE_TOKEN_FILE: (Optional) Path to store/load the OAuth token.
                         Defaults to 'vicare_token.save' in the current directory.
                         Can be overridden by the --token_file argument.
    - VICARE_DEBUG_LIB: (Optional) Set to 'true' to enable verbose logging
                        from PyViCare and underlying libraries. Defaults to 'false'.


Usage:
    python check_cooling_mode_cli.py [OPTIONS]

Options:
    -h, --help          Show this help message and exit.
    --token_file TOKEN_FILE
                        Path to the Viessmann API token file.
                        Overrides VICARE_TOKEN_FILE env var if set.
                        Default: vicare_token.save
"""
import os
import sys
import logging
import argparse
import requests # Added import
from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError, PyViCareRateLimitError

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


def initialize_vicare(token_file_path):
    """
    Initializes the PyViCare instance using credentials from environment variables
    and the provided token file path.
    """
    client_id = os.getenv('VICARE_CLIENT_ID', '1c681a9cfa03a0fe940f4fcfU6caCd8')
    email = os.getenv('VICARE_EMAIL')
    password = os.getenv('VICARE_PASSWORD')

    if not email or not password:
        logger.error("VICARE_EMAIL and VICARE_PASSWORD environment variables must be set.")
        sys.exit(1)

    # This try-except is for initWithCredentials specific errors.
    # Higher level errors (network, etc.) during API calls within PyViCare
    # will be caught by the main try-except block or by specific checks in calling functions.
    try:
        logger.info("Attempting to initialize PyViCare...")
        vicare = PyViCare()
        vicare.setCacheDuration(60)
        logger.info(f"Using Client ID: {client_id}")
        logger.info(f"Using Email: {email.split('@')[0]}@...")
        logger.info(f"Using Token File: {token_file_path}")
        logger.info("Initializing with credentials...")
        vicare.initWithCredentials(email, password, client_id, token_file_path)
        logger.info("Successfully initialized PyViCare and authenticated.")
        return vicare
    except PyViCareRateLimitError as e: # Catch rate limit during init itself
        logger.error(f"PyViCare Rate Limit Error during initialization: {e}")
        print(f"\nERROR: Viessmann API rate limit was hit during initialization. Please try again later. Details: {e}")
        sys.exit(1)
    except Exception as e: # Catch other errors during init
        logger.error(f"Error during PyViCare initialization or authentication: {e}", exc_info=True)
        print(f"\nERROR: Failed to initialize PyViCare. Details: {e}")
        sys.exit(1)

def discover_devices(vicare_instance):
    """
    Discovers and creates full Device objects from the PyViCare instance.
    May raise PyViCareRateLimitError or other requests.exceptions if API calls fail.
    """
    if not vicare_instance or not hasattr(vicare_instance, 'devices') or not vicare_instance.devices:
        logger.warning("No devices found in PyViCare instance or instance is not valid.")
        return []

    logger.info(f"Found {len(vicare_instance.devices)} device configuration(s) in the installation.")

    all_devices = []
    for device_config in vicare_instance.devices:
        try:
            logger.info(f"Processing device config: ID {device_config.id}, Type: {device_config.device_type}")
            # This .service call can trigger API requests and thus errors
            device = device_config.service
            logger.info(f"Successfully created Device object: {device.getModel()} (ID: {device_config.id}, Type: {type(device).__name__})")
            all_devices.append(device)
        except PyViCareRateLimitError: # Re-raise to be caught by main handler
            raise
        except Exception as e:
            logger.error(f"Error creating full Device object for ID {device_config.id} (Type: {device_config.device_type}): {e}", exc_info=True)
            # Optionally, continue to try other devices or re-raise

    return all_devices

def check_devices_for_cooling(devices_list):
    """
    Checks each device and its circuits for active cooling modes or programs.
    May raise PyViCareRateLimitError or other requests.exceptions if API calls fail.
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
                except PyViCareRateLimitError: raise # Re-raise
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
                    except PyViCareRateLimitError: raise # Re-raise
                    except Exception as e:
                        logger.error(f"    Error getting active program for {circuit_name} on {device.getModel()}: {e}", exc_info=True)

        except PyViCareNotSupportedFeatureError:
            logger.info(f"  Device {device.getModel()} does not support circuits or related features needed for cooling check at device level.")
        except AttributeError as e:
             logger.info(f"  Device {device.getModel()} appears to be missing the 'circuits' attribute: {e}")
        except PyViCareRateLimitError: raise # Re-raise from device-level processing
        except Exception as e:
            logger.error(f"  An error occurred while processing device {device.getModel()}: {e}", exc_info=True)

    return cooling_devices_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Viessmann Cooling Mode Check CLI using PyViCare.",
        epilog="""
Prerequisites:
- Python 3.x
- PyViCare library: pip install PyViCare
- Environment variables for authentication:
    - VICARE_EMAIL: Your Viessmann account email.
    - VICARE_PASSWORD: Your Viessmann account password.
    - VICARE_CLIENT_ID: (Optional) Your Viessmann API client ID.
                       Defaults to PyViCare's standard client ID.
    - VICARE_TOKEN_FILE: (Optional) Path to store/load the OAuth token.
                         Default can be set by --token_file.
    - VICARE_DEBUG_LIB: (Optional) Set to 'true' for verbose PyViCare logs.
""",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--token_file",
        type=str,
        default=os.getenv('VICARE_TOKEN_FILE', "vicare_token.save"),
        help="Path to the Viessmann API token file.\n"
             "Overrides VICARE_TOKEN_FILE env var if set.\n"
             "Default: vicare_token.save"
    )
    args = parser.parse_args()

    logger.info("Starting Viessmann Cooling Mode Check CLI...")

    debug_vicare_library = os.getenv('VICARE_DEBUG_LIB', 'False').lower() == 'true'
    if not debug_vicare_library:
        logger.info("Suppressing verbose PyViCare library logs. Set VICARE_DEBUG_LIB=true to enable.")
        logging.getLogger("PyViCare").setLevel(logging.WARNING)
        logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
        logging.getLogger("oauthlib").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    vicare_instance = None # Ensure defined for the finally block if init fails early
    try:
        vicare_instance = initialize_vicare(args.token_file)

        # initialize_vicare sys.exits on failure, so no need for 'if vicare_instance:' here
        # as the script would have already exited.

        logger.info("PyViCare instance created. Discovering devices...")
        devices = discover_devices(vicare_instance) # Can raise PyViCareRateLimitError

        if devices:
            logger.info(f"Successfully discovered {len(devices)} device object(s).")
            logger.info("Checking for cooling mode...")
            cooling_info = check_devices_for_cooling(devices) # Can raise PyViCareRateLimitError

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
Ensure your installation is accessible and credentials (VICARE_EMAIL, VICARE_PASSWORD) are correct and set as environment variables.
""")

    except PyViCareRateLimitError as e:
        logger.error(f"Viessmann API rate limit was hit: {e}", exc_info=True) # exc_info for context
        print(f"\nERROR: Viessmann API rate limit was hit. Please try again later. Details: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e: # Catch requests' base ConnectionError
        logger.error(f"A connection error occurred: {e}", exc_info=True)
        print(f"\nERROR: A network connection error occurred. Please check your internet connection. Details: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected critical error occurred: {e}", exc_info=True)
        print(f"\nAn unexpected critical error occurred: {e}")
        sys.exit(1)
    finally:
        logger.info("Cooling mode check finished.")
