import asyncio
import logging
import random
import math
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pui import PUIComponent
from pui.pui_config import POT_DAT
import RPi.GPIO as GPIO

# Configure logging - increase level to DEBUG for more detailed logs
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

# Global variables for potentiometer simulation
pot_value = 341  # Middle position by default
last_pot_value = 341  # Track changes

# Set GPIO mode once globally
try:
    GPIO.setmode(GPIO.BCM)
except:
    pass

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data for testing"""
    angle = 0
    
    try:
        while True:
            # Generate voltage data (sine wave with noise)
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle) + random.uniform(-0.1, 0.1)
            
            # Calculate simulated B-field - increased magnitude for better visibility
            b_field_x = math.cos(angle) * random.uniform(0.5, 1.5) * 0.0001  # 4x stronger
            b_field_y = math.sin(angle) * random.uniform(0.5, 1.5) * 0.0001
            b_field = [b_field_x, b_field_y]  # Vector form
            
            # Send signal data that matches the expected format in PUIComponent
            await q_data.put({
                "topic": "signal/data", 
                "payload": {
                    "freq": 50.0 + random.uniform(-1.0, 1.0),  # Small variations in frequency
                    "mag": abs(voltage),  # Signal magnitude
                    "phase": angle,  # Signal phase in radians
                    "ampl": abs(voltage),  # Signal amplitude
                    "bfield": b_field  # B-field vector
                }
            })
            
            # Sleep rate controls data generation speed
            await asyncio.sleep(0.2)  # 5Hz update rate

    except asyncio.CancelledError:
        logger.info("Data generation task cancelled")
    except Exception as e:
        logger.error(f"Error in data generation: {e}")

async def control_message_handler(q_control: asyncio.Queue):
    """Handle control messages sent from LCD controller"""
    while True:
        try:
            control_msg = await q_control.get()
            logger.info(f"Control message: {control_msg}")
            q_control.task_done()
        except asyncio.CancelledError:
            logger.info("Control message handler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in control message handler: {e}")
            await asyncio.sleep(1)

async def simulate_pot_change():
    """Periodically check if global pot value has changed and update LCD controller"""
    global pot_value, last_pot_value
    
    try:
        while True:
            # If pot value has changed significantly, log it
            if abs(pot_value - last_pot_value) > 10:
                logger.info(f"Potentiometer changed from {last_pot_value} to {pot_value}")
                last_pot_value = pot_value
                
            await asyncio.sleep(0.1)
            
    except asyncio.CancelledError:
        logger.info("Pot change simulator cancelled")
    except Exception as e:
        logger.error(f"Error in pot change simulator: {e}")

async def handle_user_input():
    """Handle user keyboard input for testing"""
    global pot_value
    
    print("\nManual Test Controls:")
    print("  m - Simulate mode button press")
    print("  p - Simulate power button press")
    print("  + - Increase data acquisition time")
    print("  - - Decrease data acquisition time")
    print("  d - Debug ADC and potentiometer")
    print("  q - Quit test")
    print("\nEnter command: ", end='', flush=True)
    
    while True:
        # Non-blocking input check using select
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip().lower()
            
            if cmd == 'q':
                logger.info("User requested exit")
                return True
                
            elif cmd == 'm':
                logger.info("Simulating mode button press - manually triggering")
                # Directly call the handler instead of through GPIO
                if hasattr(lcd, 'handle_button_press'):
                    await lcd.handle_button_press(17)  # BUTTON_MODE
                
            elif cmd == 'p':
                logger.info("Simulating power button press - manually triggering")
                if hasattr(lcd, 'handle_button_press'):
                    await lcd.handle_button_press(22)  # BUTTON_POWER
                
            elif cmd == '+':
                # Larger increase for more noticeable effect
                pot_value = min(1023, pot_value + 100)
                logger.info(f"Increased DAT potentiometer to {pot_value}")
                
            elif cmd == '-':
                # Larger decrease for more noticeable effect
                pot_value = max(0, pot_value - 100)
                logger.info(f"Decreased DAT potentiometer to {pot_value}")
                
            elif cmd == 'd':
                # Debug ADC and potentiometer
                logger.info(f"DEBUG: Current pot_value: {pot_value}")
                logger.info(f"DEBUG: Current voltage: {pot_value * 5.0 / 1023.0:.2f}V")
                # Test the monkey patched function directly
                from piplates import ADCplate as ADC
                value = ADC.getADC(0, POT_DAT)
                logger.info(f"DEBUG: Direct ADC.getADC(0,{POT_DAT}) call returns: {value:.2f}V")
                # Force a state change to ADJUSTING to test potentiometer handling
                logger.info("DEBUG: Forcing state change to ADJUSTING")
                lcd.current_state = 2  # State.ADJUSTING
                await lcd.update_display_with_state()
                
            print("\nEnter command: ", end='', flush=True)
            
        await asyncio.sleep(0.1)
    
    return False

async def test_pot_directly():
    """Simple periodic test of the potentiometer ADC reading"""
    try:
        from piplates import ADCplate as ADC
        
        while True:
            global pot_value
            try:
                # Read directly using our mocked function
                value = ADC.getADC(0, POT_DAT)
                logger.debug(f"Direct ADC test: pot_value={pot_value}, ADC.getADC(0,{POT_DAT})={value:.2f}V")
            except Exception as e:
                logger.error(f"Error in direct ADC test: {e}")
            
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"Failed to start ADC test: {e}")
    except asyncio.CancelledError:
        logger.info("ADC test task cancelled")

async def main():
    global lcd
    
    # Initialize queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Tasks list for proper cleanup
    tasks = []
    
    try:
        # Patch ADC.getADC BEFORE creating the PUIComponent
        from piplates import ADCplate as ADC
        original_getADC = ADC.getADC
        
        def mock_getADC(addr, chan):
            global pot_value
            if addr == 0 and chan == POT_DAT:  # Using POT_DAT from pui_config
                voltage = pot_value * 5.0 / 1023.0
                logger.debug(f"Mock ADC.getADC called: addr={addr}, chan={chan}, pot_value={pot_value}, voltage={voltage:.2f}V")
                return voltage
            return original_getADC(addr, chan)
        
        # Apply the monkey patch
        ADC.getADC = mock_getADC
        logger.info(f"Applied mock_getADC patch to ADC module using POT_DAT={POT_DAT}")

        # Create LCD controller after patching
        lcd = PUIComponent(q_data, q_control)
        logger.info(f"Created PUIComponent instance: {lcd}")
        
        # Start data generation
        data_task = asyncio.create_task(generate_test_data(q_data))
        tasks.append(data_task)
        
        # Start control message handler
        control_task = asyncio.create_task(control_message_handler(q_control))
        tasks.append(control_task)
        
        # Start potentiometer change simulator
        pot_task = asyncio.create_task(simulate_pot_change())
        tasks.append(pot_task)
        
        # Start direct ADC test
        adc_test_task = asyncio.create_task(test_pot_directly())
        tasks.append(adc_test_task)
        
        # User input handling
        user_task = asyncio.create_task(handle_user_input())
        tasks.append(user_task)
        
        # Run the LCD controller
        logger.info("Starting LCD controller test")
        logger.info("Use keyboard for manual control:")
        logger.info("  m - Toggle between B-field and FFT views")
        logger.info("  p - Toggle display power on/off")
        logger.info("  +/- - Adjust data acquisition time (larger steps now)")
        logger.info("  d - Debug ADC and potentiometer")
        logger.info("  q - Quit test")
        
        lcd_task = asyncio.create_task(lcd.run())
        tasks.append(lcd_task)
        
        # Wait until user requests exit
        await user_task
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Cleaning up...")
        
        # Restore original ADC function if we patched it
        if 'original_getADC' in locals() and 'ADC' in locals():
            try:
                ADC.getADC = original_getADC
                logger.info("Restored original ADC.getADC function")
            except Exception as e:
                logger.error(f"Error restoring ADC function: {e}")
        
        # Cancel all tasks
        for task in tasks:
            if task and not task.done():
                try:
                    task.cancel()
                except Exception as e:
                    logger.error(f"Error cancelling task: {e}")
                
        # Wait for tasks to complete
        if tasks:
            try:
                await asyncio.wait(tasks, timeout=1.0)
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}")
                
        # Ensure LCD cleanup is called
        if 'lcd' in globals() and lcd:
            try:
                await lcd.cleanup()
            except Exception as e:
                logger.error(f"Error during LCD cleanup: {e}")
            
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        # Use asyncio.run to ensure proper cleanup of event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    finally:
        # Final GPIO cleanup
        try:
            GPIO.cleanup()
        except:
            pass
