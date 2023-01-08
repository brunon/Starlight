# Pimoroni Wireless Plasma Kit - Server

This repository contains an implementation of Raspberry Pi Pico MicroPython code for the [Pimoroni Wireless Plasma Kit](https://shop.pimoroni.com/products/wireless-plasma-kit?variant=40449879081043).

Unlike the simple examples provided out of the box, this is a client/server implementation where the Pico will download its configuration from an external Web server, and automatically change its animation implementation based on the contents of the configuration file.

This repository contains both the MicroPython code to run on the Pico board, as well as a minimal web page that can be installed in Apache2 running on another Raspberry Pi.

## Web Server Setup

This part must be run on some other web server on your local network. For my testing I used a Rasbperry Pi 4 running Apache2, but any Web server capable of running PHP will do.

These instructions assume you have a Rpi4 with Apache2 already installed, if not, follow [this guide](https://magpi.raspberrypi.com/articles/apache-web-server).

### Install the web files

Create a directory in your Web server's docroot. In my case this was `/var/www/html/` so I created the following folder:

`sudo mkdir /var/www/html/starlight/`

Then, copy or symlink the following files to this web directory:

```
sudo cp /path/to/git/clone/web/{*.html,*.js,*.css,*.php} /var/www/html/starlight/
```

Finally copy the sample config.json file as a starting point:

```
sudo cp /path/to/git/clone/SAMPLE_CONFIG.json /var/www/html/starlight/config.json
```

Make sure the proid of your web server can _write_ to this file. In my case it was `www-data`:

```
sudo chown www-data.www-data /var/www/html/starlight/config.json
sudo chmod 644 /var/www/html/starlight/config.json
```

### Apache2 setup

This is optional, but it helps to prevent browser caching on the `config.json` file.

To that end, install `mod_headers` and `mod_rewrite` in Apache2:

```
sudo a2enmod rewrite
sudo a2enmod headers
```

You can then enable these using a `.htaccess` file:

```
sudo cp /path/to/git/clone/web/htaccess /var/www/html/starlight/.htaccess
```

### Test web server setup

You can try POST-ing a JSON file to the server, to test that PHP is installed correctly and all permissions are properly set up:

```
sudo apt-get install curl -y

# this assumes you installed these files under /starlight and your web server runs on port 80, if not change accordingly
curl -X POST -v -d @/path/to/git/clone/SAMPLE_CONFIG.json 'http://localhost:80/starlight/post_config.php'
```

This should update the `config.json` file and return:

```json
{"success": true}
```

## Configure the Plasma Kit Light

Open Thonny, and copy the contents of the `pico/starlight.py` file into the `main.py` file on the Pico.

Edit the `WIFI_CONFIG.py` file that comes with the Plaska Kit and enter your WiFi network's `SSID`, password and country code.

Finally, at the top of the `main.py` file you just created, modify the `CONFIG_JSON_URL` constant to point to the IP/Port of the Web server you configured above.

Then plug this in and enjoy!


## How does this work?

It's simple: the Pico will ping the URL you configure every 10 seconds and look for a modified configuration file. 

If it detects a change to the configuration file, it will stop the current animation, and start off a new one. This can include changing the animation mode, or just tweaking some of the configurable settings of individual animation algorithms (such as the color codes to use, etc).

To make changes, navigate to the `index.html` page on the Web server configured above, and pick a different animation in the dropdown.

The JavaScript code will automatically POST an updated configuration file to the server, replacing the file stored on the server, and triggering the light to change within 10 seconds.

For now only the animation mode can be changed, but I plan to add some code to auto-generate form controls in the Web page to open up all the individual settings to be modified.

Contributions welcome!

