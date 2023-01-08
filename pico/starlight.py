import WIFI_CONFIG
from network_manager import NetworkManager
import uasyncio
import urequests
import time
import json
import select
import plasma
from plasma import plasma_stick
from machine import Pin
from random import uniform, random, choice
from math import sin


# Set how many LEDs you have
NUM_LEDS = 50

# URL for the server hosting the config.json file
# (change this with the path to your hosted config file)
CONFIG_JSON_URL = "http://10.0.0.205:80/starlight/config.json"
CONFIG_JSON_UPDATE_INTERVAL = 10  # seconds between checks for the config file, change as needed

# set up the Pico W's onboard LED
pico_led = Pin('LED', Pin.OUT)

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, 0, 0, plasma_stick.DAT, color_order=plasma.COLOR_ORDER_RGB)


#
# Util methods
#

def _hex_to_rgb(hex):
    # converts a hex colour code into RGB
    h = hex.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b


def rgb_to_hsv(r, g, b):
    r, g, b = r/255.0, g/255.0, b/255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    if mx == 0:
        s = 0
    else:
        s = (df/mx)*100
    v = mx*100
    return h, s, v


def download_json_file(url):
    # flash the onboard LED while loading the config
    pico_led.value(True)
    try:
        # download from the server
        print(f'Requesting URL: {url}')
        r = urequests.get(url)

        # open the json data
        j = r.json()
        print('Config data obtained!')
        r.close()
        
        return j
    finally:
        pico_led.value(False)


def download_json_file_if_elapsed(url, last_checked, min_elapsed_time_ms):
    now = time.ticks_ms()
    if last_checked is None or time.ticks_diff(now, last_checked) > min_elapsed_time_ms:
        j = download_json_file(url)
        return j
    else:
        return None
        
#
# Animation classes
#

class Animation():
    
    keep_running = True
    
    @property
    def config_key(self):
        pass

    def should_continue(self):
        return self.keep_running
    
    def stop(self):
        self.keep_running = False
        
    def start(self):
        self.keep_running = True
    
    def run(self, config):
        pass


class ErrorAnimation(Animation):
    
    @property
    def config_key(self):
        return 'error'
    
    def run(self, config):
        while True:
            for i in range(NUM_LEDS):
                led_strip.set_rgb(i, 255, 0, 0)
                time.sleep(0.02)
            for i in range(NUM_LEDS):
                led_strip.set_rgb(i, 0, 0, 0)
                
            yield


class SpookyRainbows(Animation):
    """
    Taken from: https://github.com/pimoroni/pimoroni-pico/tree/main/micropython/examples/plasma_stick
    """

    @property
    def config_key(self):
        return 'spooky_rainbows'

    def run(self, config):
        HUE_START = config.get('hue_start', 30)
        HUE_END = config.get('hue_end', 140)
        SPEED = config.get('speed', 0.3)

        distance = 0.0
        direction = SPEED
        while self.should_continue():
            for i in range(NUM_LEDS):
                # generate a triangle wave that moves up and down the LEDs
                j = max(0, 1 - abs(distance - i) / (NUM_LEDS / 3))
                hue = HUE_START + j * (HUE_END - HUE_START)

                led_strip.set_hsv(i, hue / 360, 1.0, 0.8)

            # reverse direction at the end of colour segment to avoid an abrupt change
            distance += direction
            if distance > NUM_LEDS:
                direction = - SPEED
            if distance < 0:
                direction = SPEED

            yield  # check server config file
            time.sleep(0.01)


class CheerLights(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/cheerlights.py
    """
    
    @property
    def config_key(self):
        return 'cheerlights'

    def run(self, config):
        '''
        This Plasma Stick example sets your LED strip to the current #cheerlights colour.
        Find out more about the Cheerlights API at https://cheerlights.com/
        '''
        URL = 'http://api.thingspeak.com/channels/1417/field/2/last.json'
        UPDATE_INTERVAL = config.get('refresh_interval', 120)  # in seconds
        UPDATE_INTERVAL_MS = UPDATE_INTERVAL * 1000
        last_checked = None
        while self.should_continue():
            # we only check if the elapsed time exceed our threshold
            cheerlights_json = download_json_file_if_elapsed(URL, last_checked, UPDATE_INTERVAL_MS)
            if cheerlights_json:
                last_checked = time.ticks_ms()

                # flash the onboard LED after getting data
                pico_led.value(True)
                time.sleep(0.2)
                pico_led.value(False)

                # extract hex colour from the data
                hex = cheerlights_json['field2']

                # and convert it to RGB
                r, g, b = _hex_to_rgb(hex)

                # light up the LEDs
                for i in range(NUM_LEDS):
                    led_strip.set_rgb(i, r, g, b)
                print(f'LEDs set to {hex}')

            yield  # check server config file


class Fire(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/fire.py
    """
    
    @property
    def config_key(self):
        return 'fire'
    
    def run(self, config):
        """
        A basic fire effect.
        """
        while self.should_continue():
            # fire effect! Random red/orange hue, full saturation, random brightness
            for i in range(NUM_LEDS):
                led_strip.set_hsv(i, uniform(0.0, 50 / 360), 1.0, random())

            yield  # check server config file

            time.sleep(0.1)


# utility class for animations which maintain "current_leds" and "target_leds" arrays
class AbstractMoveAnimation(Animation):

    # Create a list of [r, g, b] values that will hold current LED colours, for display
    current_leds = [[0] * 3 for i in range(NUM_LEDS)]

    # Create a list of [r, g, b] values that will hold target LED colours, to move towards
    target_leds = [[0] * 3 for i in range(NUM_LEDS)]

    def display_current(self):
        # paint our current LED colours to the strip
        for i in range(NUM_LEDS):
            led_strip.set_rgb(i, self.current_leds[i][0], self.current_leds[i][1], self.current_leds[i][2])

    def move_to_target(self, fade_up_speed, fade_down_speed):
        # nudge our current colours closer to the target colours
        for i in range(NUM_LEDS):
            for c in range(3):  # 3 times, for R, G & B channels
                if self.current_leds[i][c] < self.target_leds[i][c]:
                    self.current_leds[i][c] = min(self.current_leds[i][c] + fade_up_speed, self.target_leds[i][c])  # increase current, up to a maximum of target
                elif self.current_leds[i][c] > self.target_leds[i][c]:
                    self.current_leds[i][c] = max(self.current_leds[i][c] - fade_down_speed, self.target_leds[i][c])  # reduce current, down to a minimum of target


class Snow(AbstractMoveAnimation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/snow.py
    """
    
    @property
    def config_key(self):
        return 'snow'
    
    def run(self, config):
        # How much snow? [bigger number = more snowflakes]
        SNOW_INTENSITY = config.get('snow_intensity', 0.0002)

        # Change RGB colours here (RGB colour picker: https://g.co/kgs/k2Egjk )
        BACKGROUND_COLOUR = config.get('background_colour', [30,50,50])
        SNOW_COLOUR = config.get('snow_colour', [240,255,255])

        # how quickly current colour changes to target colour [1 - 255]
        FADE_UP_SPEED = config.get('fade_up_speed', 255)
        FADE_DOWN_SPEED = config.get('fade_down_speed', 1)

        while self.should_continue():
            for i in range(NUM_LEDS):
                # randomly add snow
                if SNOW_INTENSITY > uniform(0, 1):
                    # set a target to start a snowflake
                    self.target_leds[i] = SNOW_COLOUR
                # slowly reset snowflake to background
                if self.current_leds[i] == self.target_leds[i]:
                    self.target_leds[i] = BACKGROUND_COLOUR
            self.move_to_target(FADE_UP_SPEED, FADE_DOWN_SPEED)   # nudge our current colours closer to the target colours
            self.display_current()  # display current colours to strip

            yield  # check server config file


class Sparkles(AbstractMoveAnimation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/sparkles.py
    """
    
    @property
    def config_key(self):
        return 'sparkles'
    
    def run(self, config):
        """
        A festive sparkly effect. Play around with BACKGROUND_COLOUR and SPARKLE_COLOUR for different effects!
        """

        # How many sparkles? [bigger number = more sparkles]
        SPARKLE_INTENSITY = config.get('sparkle_intensity', 0.005)

        # Change RGB colours here (RGB colour picker: https://g.co/kgs/k2Egjk )
        BACKGROUND_COLOUR = config.get('background_colour', [50,50,0])
        SPARKLE_COLOUR = config.get('sparkle_colour', [255,255,0])

        # how quickly current colour changes to target colour [1 - 255]
        FADE_UP_SPEED = config.get('fade_up_speed', 2)
        FADE_DOWN_SPEED = config.get('fade_down_speed', 2)

        while self.should_continue():
            for i in range(NUM_LEDS):
                # randomly add sparkles
                if SPARKLE_INTENSITY > uniform(0, 1):
                    # set a target to start a sparkle
                    self.target_leds[i] = SPARKLE_COLOUR
                # for any sparkles that have achieved max sparkliness, reset them to background
                if self.current_leds[i] == self.target_leds[i]:
                    self.target_leds[i] = BACKGROUND_COLOUR
            self.move_to_target(FADE_UP_SPEED, FADE_DOWN_SPEED)   # nudge our current colours closer to the target colours
            self.display_current()  # display current colours to strip

            yield  # check server config file

        
class AlternatingBlinkies(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/alternating-blinkies.py
    """
    
    @property
    def config_key(self):
        return 'alternating_blinkies'
    
    def run(self, config):
        """
        This super simple example sets up two alternating colours, great for festive lights!
        """

        # Pick two hues from the colour wheel (from 0-360°, try https://www.cssscript.com/demo/hsv-hsl-color-wheel-picker-reinvented/ )
        HUE_1 = config.get('hue1', 40)
        HUE_2 = config.get('hue2', 205)

        # Set up brightness (between 0 and 1)
        BRIGHTNESS = config.get('brightness', 0.5)

        # Set up speed (wait time between colour changes, in seconds)
        SPEED = config.get('speed', 1)

        while self.should_continue():
            for i in range(NUM_LEDS):
                # the if statements below use a modulo operation to identify the even and odd numbered LEDs
                if (i % 2) == 0:
                    led_strip.set_hsv(i, HUE_1 / 360, 1.0, BRIGHTNESS)
                else:
                    led_strip.set_hsv(i, HUE_2 / 360, 1.0, BRIGHTNESS)
            time.sleep(SPEED)

            for i in range(NUM_LEDS):
                if (i % 2) == 0:
                    led_strip.set_hsv(i, HUE_2 / 360, 1.0, BRIGHTNESS)
                else:
                    led_strip.set_hsv(i, HUE_1 / 360, 1.0, BRIGHTNESS)
            time.sleep(SPEED)
            yield  # check server config file


class Pulse(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/pulse.py
    """
    
    @property
    def config_key(self):
        return 'pulse'
    
    def run(self, config):
        """
        Simple pulsing effect generated using a sine wave.
        """

        # we're using HSV colours in this example - find more at https://colorpicker.me/
        # to convert a hue that's in degrees, divide it by 360
        COLOUR = config.get('colour', 0.5)
        
        # config properties to adjust the implementation
        ADJUST_BRIGHTNESS = config.get('adjust_brightness', false)
        ADJUST_SATURATION = config.get('adjust_saturation', false)

        offset = 0

        while self.should_continue():
            # use a sine wave to set the brightness
            for i in range(NUM_LEDS):
                led_strip.set_hsv(i, COLOUR, 1.0, sin(offset))
            offset += 0.002

            # our sine wave goes between -1.0 and 1.0 - this means the LEDs will be off half the time
            # this formula forces the brightness to be between 0.0 and 1.0
            if ADJUST_BRIGHTNESS:
                for i in range(NUM_LEDS):
                    led_strip.set_hsv(i, COLOUR, 1.0, (1 + sin(offset)) / 2)
                offset += 0.002

            # adjust the saturation instead of the brightness/value
            if ADJUST_SATURATION:
                for i in range(NUM_LEDS):
                    led_strip.set_hsv(i, COLOUR, (1 + sin(offset)) / 2, 0.8)
                offset += 0.002

            yield  # check server config file


class Rainbows(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/rainbows.py
    """
    
    @property
    def config_key(self):
        return 'rainbows'

    def run(self, config):
        """
        Make some rainbows!
        """

        # The SPEED that the LEDs cycle at (1 - 255)
        SPEED = config.get('speed', 20)

        # How many times the LEDs will be updated per second
        UPDATES = config.get('updates', 60)
        
        BRIGHTNESS = config.get('brightness', 100)  # 1-100

        offset = 0.0

        # Make rainbows
        while self.should_continue():
            SPEED = min(255, max(1, SPEED))
            offset += float(SPEED) / 2000.0

            for i in range(NUM_LEDS):
                hue = float(i) / NUM_LEDS
                led_strip.set_hsv(i, hue + offset, 1.0, BRIGHTNESS / 100.0)

            yield  # check server config file
            time.sleep(1.0 / UPDATES)


class Tree(Animation):
    """
    Source: https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/examples/plasma_stick/tree.py
    """
    
    @property
    def config_key(self):
        return 'tree'
    
    def run(self, config):
        """
        A Christmas tree, with fairy lights!
        This will probably work better if your LEDs are in a vaguely tree shaped bottle :)
        """

        # we're using HSV colours in this example - find more at https://colorpicker.me/
        # to convert a hue that's in degrees, divide it by 360
        TREE_COLOUR = config.get('tree_colour', [0.34,1,0.6])
        LIGHT_RATIO = config.get('light_ratio', 8)
        LIGHT_COLOURS = config.get('light_colours', [ [0,1,1], [0.1,1,1], [0.6,1,1], [0.05,0.4,1] ])
        LIGHT_CHANGE_CHANCE = config.get('light_change_chance', 0.5)
    
        if config.get('error'): raise RuntimeError('error!')

        # initial setup
        for i in range(NUM_LEDS):
            if i % LIGHT_RATIO == 0:  # add an appropriate number of lights
                led_strip.set_hsv(i, *choice(LIGHT_COLOURS))  # choice randomly chooses from a list
            else:  # GREEN
                led_strip.set_hsv(i, *TREE_COLOUR)

        # animate
        while self.should_continue():
            for i in range(NUM_LEDS):
                if (i % LIGHT_RATIO == 0) and (random() < LIGHT_CHANGE_CHANCE):
                    led_strip.set_hsv(i, *choice(LIGHT_COLOURS))

            yield  # check server config file

            time.sleep(0.5)


# WiFi Setup method
def setup_wifi():
    def _wifi_status_handler(mode, status, ip):
        # reports wifi connection status
        print(mode, status, ip)
        print('Connecting to wifi...')
        # flash while connecting
        for i in range(NUM_LEDS):
            led_strip.set_rgb(i, 255, 255, 255)
            time.sleep(0.02)
        for i in range(NUM_LEDS):
            led_strip.set_rgb(i, 0, 0, 0)
        if status is not None:
            if status:
                print(f'Successfully connected to SSID {WIFI_CONFIG.SSID}')
            else:
                raise RuntimeError('Wifi connection failed!')

    network_manager = NetworkManager(WIFI_CONFIG.COUNTRY, status_handler=_wifi_status_handler)
    uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))


def load_config_file():
    try:
        # try to download the config file from the server
        config_json = download_json_file(CONFIG_JSON_URL)
        
        # save the JSON file locally (as a backup)
        with open('config.json', 'w') as file:
            json.dump(config_json, file)
            
        return config_json
            
    except Exception as e:
        print(f"Error downloading config.json from {CONFIG_JSON_URL}: {e}")
        
        # try to load the config saved locally as a backup
        config_file_names = ['config.json', 'SAMPLE_CONFIG.json']
        for file_name in config_file_names:
            try:
                with open(file_name, 'r') as file:
                    print(f'Loading config saved locally in file {file_name}')
                    return json.load(file)
            except OSError:
                pass  # ignore if file does not exist, move on to the next one
            
        raise RuntimeError(f"none of the supported config files exist: {', '.join(config_file_names)}")
        

def load_animation_from_config(config):
    # if we have a saved animation, pick that
    if 'current_animation' in config and config['current_animation'] in ALL_ANIMATIONS:
        current_animation = ALL_ANIMATIONS[config['current_animation']]
    else:
        # otherwise pick one at random
        current_animation = choice(list(ALL_ANIMATIONS.values()))
        print(f"No saved animation, picked {current_animation.config_key} at random")

    if current_animation.config_key not in config:
        raise RuntimeError(f'config.json file does not contain a section for {current_animation.config_key}')
    else:
        animation_config = config[current_animation.config_key]
        
    return current_animation, animation_config


# all the animation classes, indexed by config key name
ALL_ANIMATIONS = {
    a.config_key: a
    for a in [
        # add animation classes here as needed
        SpookyRainbows(),
        CheerLights(),
        Fire(),
        Snow(),
        Sparkles(),
        AlternatingBlinkies(),
        Pulse(),
        Rainbows(),
        Tree()
        ]
    }

if __name__ == '__main__':
    # start updating the LED strip
    led_strip.start()

    # first things first: we need WiFi
    setup_wifi()

    # load configuration file from server (or local cache if server is down)
    config = load_config_file()
    last_updated = time.ticks_ms()

    # load initial animation
    current_animation, animation_config = load_animation_from_config(config)

    while True:
        # loop forever and every time the animation code does a "yield", we have an opportunity to check the server's config.json file
        current_animation.start()
        
        try:
            # start the animation, which will parse the config object
            # this might fail if the config is missing mandatory keys
            animation_iter = current_animation.run(animation_config)
            
            # loop once to trigger any errors in the run() function
            next(animation_iter)
            
        except Exception as e:
            print(f'Animation failed to run: {e}')
            current_animation = ErrorAnimation()  # run a safe default while waiting for a new, fixed config

        for _ in animation_iter:
            # inside this loop we're at a point where the animation code did a "yield"
            # try to download a new config file
            try:
                new_config = download_json_file_if_elapsed(CONFIG_JSON_URL, last_updated, CONFIG_JSON_UPDATE_INTERVAL * 1000)

                # if we didn't get new json (not enough time has passed since last check) then we do nothing and continue
                if new_config is None:
                    continue

            except Exception as e:
                print(f'Error downloading new config from server: {e}')
                continue  # ignore and continue with existing config
            
            # remember the time we last checked (to ensure we don't check again right away)
            last_updated = time.ticks_ms()
            
            # then, if the data we got differs from the current config, we switch animations
            if new_config != config:
                # first stop the current animation (this will terminate the run() loop)
                current_animation.stop()
                try:
                    # then load a new animation
                    current_animation, animation_config = load_animation_from_config(new_config)
                    print(f"Now running new animation {current_animation.config_key}")
                    config = new_config
                except Exception as e:
                    # ignore errors and keep old config
                    print(f'Error initializing new animation: {e}')
                finally:
                    break  # exit out of the run() loop and start a new animation loop
            else:
                print('Config unchanged, keeping current animation')

