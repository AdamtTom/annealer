import esp32
nvs = esp32.NVS("annealer")
targettemperature = 500
try:
    targettemperature = nvs.get_i32('targettemp')
except:
    pass

hysteresis = 3
try:
    hysteresis = nvs.get_i32('hysteresis')
except:
    pass

holdminutes = 60
try:
    holdminutes = nvs.get_i32('holdminutes')
except:
    pass

from machine import Pin
import neopixel
np = neopixel.NeoPixel(Pin(8), 1)

brightness = 0.1
def scaled():
    return int(255*brightness)

def npoff():
    np[0] = (0,0,0)
    np.write()

def npred():
    np[0] = (scaled(),0,0)
    np.write()

def npgreen():
    np[0] = (0,scaled(),0)
    np.write()

def npblue():
    np[0] = (0,0,scaled())
    np.write()

def npcyan():
    np[0] = (0, scaled(),scaled())
    np.write()

def npmagenta():
    np[0] = (scaled(),0,scaled())
    np.write()

def npyellow():
    np[0] = (scaled(),scaled(),0)
    np.write()

def npwhite():
    np[0] = (scaled(),scaled(),255*brightness)
    np.write()

def npoff():
    np[0] = (0,0,0)
    np.write()

outpin = Pin(7, Pin.OUT)
outpin.off()

import wifi_credentials as WiFi
import network, time
import urequests as requests

sta=network.WLAN(network.STA_IF)
sta.active(True)

haveWiFi = False
logging = False

def connect_wifi():
    try:
        if WiFi.IP != 'DHCP':
            sta.ifconfig((WiFi.IP, WiFi.netmask, WiFi.gateway, WiFi.DNS))
        if not sta.isconnected():
            sta.connect(WiFi.SSID, WiFi.Password)
    except Exception as e:
        print(e)
        blink(npcyan, npred)
    global haveWiFi, logging
    for i in range(6):
        if sta.isconnected():
            print("Connected to " + sta.ifconfig()[0])
            haveWiFi = True
            logging = True
            break;
        if i == 5:
            print("Connection failed")
            haveWiFi = False
            logging = False
        time.sleep(1)

import max31855
temperature = max31855.MAX31855(so_pin=4, cs_pin=5, sck_pin=6)

# Setup Adafruit IO
temperature_feed_name = "annealingkiln.temperature"
status_feed_name = "annealingkiln.status"
import aio_credentials as AIO
# import clicksend_credentials as ClickSend
import gmail_credentials as gmail
import umail

pn = '8082818386'
temperature_url = 'https://io.adafruit.com/api/v2/' + AIO.USERNAME + '/feeds/' + temperature_feed_name + '/data'
status_url = 'https://io.adafruit.com/api/v2/' + AIO.USERNAME + '/feeds/' + status_feed_name + '/data'

# # TxtDrop does not work because they seem to think I am still on Verizon
# def sendSMSTxtDrop(msg):
#     # headers = {'X-AIO-Key': AIO.KEY, 'Content-Type': 'application/json'}
#     body = {'number': "279z5p2tg17j", 'body': msg}
#     try:
#         r = requests.post("http://www.txtdrop.com/send.php", json=body)
#         print(r.text)
#         r.close()
#     except Exception as e:
#         print("sendSMSTxtDrop", e)
# 
# clicksend_url = 'https://api-mapper.clicksend.com/http/v2/send.php?method=http&username=' + ClickSend.USERNAME + '&key=' + ClickSend.KEY + '&to=' + pn + '&message=The%20kiln%20is%20'
# # Send with ClickSend
# def sendSMSClickSend(msg):
#     try:
#         msg_url = clicksend_url + msg
#         r = requests.get(msg_url)
#         print(msg_url)
#         if r.status_code != 200:
#             print("sendSMS failed with status", r.reason, " - ", r.text)
#         r.close()
#     except Exception as e:
#         print("SendSMS", e)

sender_email = gmail.USERNAME
sender_key = gmail.KEY
recipient_email = pn + "@tmomail.net"
def sendSMS(msg):
    smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True) # Gmail's SSL port
    smtp.login(sender_email, sender_key)
    smtp.to(recipient_email)
    smtp.write("From: HonuPuttersIoT" + "<"+ sender_email+">\n")
    smtp.write("Subject: Kiln Status\n")
    smtp.write(msg)
    smtp.send()
    smtp.quit()

def blink(color1, color2):
    while True:
        color1()
        time.sleep(0.5)
        color2()
        time.sleep(0.5)

npcyan()
connect_wifi()
if not haveWiFi:
    blink(npmagenta, npcyan)
npmagenta()
time.sleep(1)

def aioStatus(state):
    if logging:
        headers = {'X-AIO-Key': AIO.KEY, 'Content-Type': 'application/json'}
        status_body = {'value': state}
        try:
            r = requests.post(status_url, json=status_body, headers=headers)
            print(r.text)
            r.close()
        except Exception as e:
            print("aioStatus", e)

state = "Heating"

statestart = 0

def notify(state):
    aioStatus(state)
    sendSMS(state)
    print('The kiln is', state)

degreesC = 0
degreesF = 0

minutes = 0
last_minutes = -1
def log_to_aio():
    global last_minutes, minutes
    if minutes != last_minutes:
        last_minutes = minutes
        if logging:
            headers = {'X-AIO-Key': AIO.KEY, 'Content-Type': 'application/json'}
            temperature_body = {'value': str(degreesC)}
            try:
                r = requests.post(temperature_url, json=temperature_body, headers=headers)
                print(r.text)
                r.close()
            except Exception as e:
                print("AIO log temperature", e)
            gc.collect()

temperature_errors = 0

def TC_no_interface():
    global outpin
    outpin.off()
    state = "Broken"
    notify("Broken-No_TC_Interface")
    blink(npyellow, npoff)

def getTemperature():
    global degreesC, degreesF, state, temperature_errors, outpin
    try:
        degreesF = round(temperature.readFahrenheit())
        degreesC = round(temperature.readCelsius())
    except:
        degreesF = -1
        degreesC = -1
    if temperature.data == 0:
        temperature_errors = temperature_errors + 1
        if temperature_errors >= 5:
            TC_no_interface()
    elif (degreesC < 2):
        print("Error", hex(temperature.data))
    else:
        print(degreesF, degreesC)
    if degreesC == 0:
        msg = ""
        if temperature.noConnection:
            msg = "TC_not_connected"
        if temperature.shortToGround:
            msg = "TC_shorted_to_ground"
        if temperature.shortToVCC:
            msg = "TC_shorted_to_VCC"
        if temperature.unknownError:
            msg = "TC_unknown_error"
        if msg != "":
            outpin.off()
            state = "Broken"
            notify("Broken-" + msg)
            blink(npred, npoff)

def TC_check_interface():
    data = 0
    for i in range(5):
        temperature.read()
        data = data + temperature.data
    if data == 0:
        TC_no_interface()
    global degreesC
    getTemperature()

def time_minutes():
    return time.ticks_ms()//60000

def kiln_init():
    global outpin,statestart
    TC_check_interface()
    npred()
    print("Turning on outpin")
    outpin.on()
    state = 'Heating'
    statestart = time_minutes()
    notify(state)

def kiln_step():
    global degreesC, degreesF, minutes, state, statestart
    global outpin
    gc.collect()
    getTemperature()
    gc.collect()
    minutes = time_minutes()
    if state == "Heating":
        npred()
        if degreesC > targettemperature:
            state = "Holding"
            notify(state)
            outpin.off()
            statestart = minutes
    elif state == "Holding":
        if (minutes - statestart) >= holdminutes:
            state = "Cooling"
            statestart = minutes
            notify(state)
            outpin.off()
        elif degreesC > targettemperature:
            npyellow()
            outpin.off()
        elif degreesC >= 2 and degreesC < (targettemperature - hysteresis):
            npgreen()
            outpin.on()
    elif state == "Cooling":
        npblue()
    log_to_aio()

def kiln():
    kiln_init()
    while True:
        kiln_step()
        time.sleep(1)

import microdot_wmb as microdot

server = microdot.Microdot()
# microdot.Request.socket_read_timeout = 0.1

def page():
    global output, statestart
    heating = 'On' if outpin.value() else 'Off'
    return '''<meta http-equiv="refresh" content="60">
        <form action="" method="POST" target='_blank'><div><font size="+2">''' +\
        state + ' at ' + str(degreesC) + 'C for ' + str(time_minutes() - statestart) + ' minutes with heater ' + heating + \
        '''</font></div><br>
        <div><label for="targettemperature">Target Temperature C:</label>
        <input type="number" id="targettemperature" name="targettemperature" min="25" max="1000" value="''' +\
        str(targettemperature) + '''"></div>
        <div><label for="hysteresis">Hysteresis:</label>
        <input type="number" id="hysteresis" name="hysteresis" min="1" max="20" value="''' +\
        str(hysteresis) + '''"></div>
        <div><label for="holdminutes">Minutes:</label>
        <input type="number" id="holdminutes" name="holdminutes" min="1" max="200" value="''' +\
        str(holdminutes) + '''"></div>
        <input type=submit value="Set">
        </form>'''

@server.route('/', methods=['GET', 'POST'])
def hello(request):
    global state, degreesC
    global targettemperature, hysteresis, holdminutes
    # return state + ' ' + str(degreesC)
    if request.method == 'GET':
        return page(), 200, {'Content-Type': 'text/html'}
    elif request.method == 'POST':
        print(request.body)
        targettemperature = int(request.form.get('targettemperature'))
        hysteresis = int(request.form.get('hysteresis'))
        holdminutes = int(request.form.get('holdminutes'))
        nvs.set_i32('targettemp', targettemperature)
        nvs.set_i32('hysteresis', hysteresis)
        nvs.set_i32('holdminutes', holdminutes)
        nvs.commit()
        return 'Target temperature set to ' + str(targettemperature) + '/' + str(hysteresis) + ' for ' + str(holdminutes) + ' minutes'

# @server.post('/config')
# def setconfig(request):
#     print(request)

from sys import print_exception

try:
    kiln_init()
    server.run(hook=kiln_step, hooktime=1.0)
    # server.run()
    # kiln()
except Exception as e:
    # print("Crashed " + e)
    print("Crashed", e)
    print_exception(e)
