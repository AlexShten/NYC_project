import os
import sys
import threading
import time
import copy
from datetime import datetime

import RPi.GPIO as GPIO
import smbus
from w1thermsensor import W1ThermSensor

from pyowm import OWM
import sqlite3
import psycopg2
from psycopg2 import extensions, connect, InterfaceError, DatabaseError, OperationalError

# ----------------------------------------------------------
local_dbname = '/home/pi/dataDB'

server_host = '47.18.165.54'
server_dbname = 'production'
server_username = 'maksym'
server_password = 'Cj75mrwBM2yXgVnnW4ug'

SN = sys.argv[1]  # "Test_SN_UA"# read from file
TZ = "UTC"
path_to_file = "/home/pi/sensorsID.txt"
cmd = "reboot"

quantity_temp_sens = 7  # read from file
# ----------------------------------------------------------
# FLAGs
read_vars_thread_status = 0
write_data_thread_status = 0
write_error_thread_status = 2
db_thread_status = 0
check_thread_status = 0
to_db_status = 0
from_db_status = 0
db_start = 0
set_WiFi = 0
update = 0
main = 0
led = 0
adc = 0
retries = 0
WIFI_LED_ON = 1
var = 0
restart = 0
connection_for_data_and_variables = None
variables_list = [2, 2, 2, 2, 2, "0", "0"]
variables_list_old = [2, 2, 2, 2, 2]
weather_timer = 2000
watchdog = 0

reset_temp_repeat = 0

wait_times = [60, 60, 900, 1800, 3600]
wait_wifi = 0
wifi_recconnect_repeat = 0
wifi_recconnect_flag = 0

bias = 16
last_bias = 0

therm_bits = 0
pump_bits = 0

correct_variables = range(9)


numbers = 7200
Quant = 0
# ---------------------------2-auto, 1-ON, 0-OFF
variable_RT1 = 2
variable_RT2 = 2
variable_RT3 = 2
variable_BLR = 2
variable_all_OFF = 2
variable_wifiid = 0
variable_wifipass = 0
# ---------------------------
data_sn = SN
data_time = 0
data_zone = TZ
data_boilerpumpfunamps = 0
data_ics1 = 0
data_ics2 = 0
data_ics3 = 0
data_t1 = 0
data_t2 = 0
data_t3 = 0
data_t4 = 0
data_t5 = 0
data_t6 = 0
data_t7 = 0
data_ps = 0
data_rt1 = 0
data_rt2 = 0
data_rt3 = 0
data_boiler = 0
data_end = 0
data_wt = 0
# ---------------------------
error_sn = SN
error_time = 0
error_boilercurrent = 0
error_ics1 = 0
error_ics2 = 0
error_ics3 = 0
error_t1 = 0
error_t2 = 0
error_t3 = 0
error_t4 = 0
error_t5 = 0
error_t6 = 0
error_t7 = 0
error_wt = 0
error_relay1 = 0
error_relay2 = 0
error_relay3 = 0
error_relay4 = 0
error_relay5 = 0
error_relay6 = 0
error_relay7 = 0

main_db_data_list = []
inner_db_data_list = [None] * 20
inner_db_data_list_copy = []
# ---------------------------
available_sensors = [None] * 7
sensors_in_system = [None] * 7


def Print_error(Source, Error):
    print(" ")
    print(Source)
    print(time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()))
    print(Error)


def System_tick_1_sec():
    global write_data_thread_status, read_vars_thread_status, db_thread_status, main, adc, weather_timer, watchdog, update, set_WiFi, wifi_recconnect_flag, wait_wifi

    MAIN_TIME_LAST = 0
    while True:

        MAIN_TIME_NEXT = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())
        if MAIN_TIME_NEXT != MAIN_TIME_LAST:
            write_data_thread_status = 1
            read_vars_thread_status = 1
            db_thread_status = 1
            main = 1
            adc = 1
            weather_timer += 1

            if wifi_recconnect_flag == 1:
                wait_wifi += 1

            if check_thread_status == 0 and update == 0 and set_WiFi == 0:
                watchdog += 1

            MAIN_TIME_LAST = MAIN_TIME_NEXT


def System_tick_05_sec():
    global led

    TIME_LAST = 0
    while True:

        TIME_NEXT = time.perf_counter()
        if TIME_NEXT - TIME_LAST >= 0.5:
            led = 1

            TIME_LAST = TIME_NEXT


# ----------------------------------------------------------------------------------------------------

# def DB_switch_LOCAL_EXTERNAL():


def DB_switch_EXTERNAL_LOCAL():
    global to_db_status, check_thread_status, WIFI_LED_ON
    global variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF
    to_db_status = 1
    check_thread_status = 1
    WIFI_LED_ON = 1
    variable_RT1 = 2  # auto
    variable_RT2 = 2  # auto
    variable_RT3 = 2  # auto
    variable_BLR = 1  # on
    variable_all_OFF = 2  # auto


def Create_connection():
    global server_host, server_dbname, server_username, server_password
    global connection_for_data_and_variables, cursor, WIFI_LED_ON
    if connection_for_data_and_variables == None:
        try:
            connection_for_data_and_variables = psycopg2.connect(host=server_host, database=server_dbname,
                                                                 user=server_username, password=server_password,
                                                                 connect_timeout=2)  # , connect_timeout=1, options='-c statement_timeout=1000')
            if connection_for_data_and_variables != None:
                cursor = connection_for_data_and_variables.cursor()
                WIFI_LED_ON = 0
        #             else:
        #                 DB_switch_EXTERNAL_LOCAL()
        #                 print("else1")
        except psycopg2.OperationalError as e:
            pass
            # Print_error("Connection create error", e)
            # DB_switch_EXTERNAL_LOCAL()
            # print("else2")


def Request_data_to_server():
    global server_host, server_dbname, server_username, server_password
    global connection_for_data_and_variables, cursor, WIFI_LED_ON, set_WiFi, variables_list, update
    global write_data_thread_status, read_vars_thread_status, check_thread_status, to_db_status, from_db_status, WIFI_LED_ON, retries, watchdog, therm_bits, pump_bits

    global variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF, variable_wifiid, variable_wifipass, correct_variables

    global data_sn, data_time, data_zone, data_boilerpumpfunamps, data_boiler, data_ics1, data_ics2, data_ics3
    global data_t1, data_t2, data_t3, data_t4, data_t5, data_t6, data_t7, data_ps, data_rt1, data_rt2, data_rt3
    global data_wt, data_end

    while retries < 10:
        pass

    check_thread_status = 0
    connection_for_data_and_variables = None
    Create_connection()

    while True:

        if write_data_thread_status == 1 and set_WiFi == 0 and update == 0:

            # print(connection_for_data_and_variables.isolation_level)

            data_time = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())
            data_list = (
                data_sn, data_time, data_zone, data_boilerpumpfunamps, data_ics1, data_ics2, data_ics3, data_boiler,
                data_t1, data_t2, data_t3, data_t4, data_t5, data_t6, data_t7, data_rt1, data_rt2, data_rt3, data_end,
                data_ps, data_wt)
            # print(data_list)
            if to_db_status == 0 and from_db_status == 0:
                try:
                    try:
                        #                         print("1")
                        #                         print(time.perf_counter())
                        #                         print("---------")
                        cursor.execute('INSERT INTO \
                            devicedata (sn, time, zone, icsmain, icsz1, icsz2, icsz3, \
                            icsboiler, t1, t2, t3, t4, t5, t6, t7, rt1, rt2, rt3, endswitch, ps, weather) \
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);', data_list)
                    except psycopg2.DatabaseError as e:
                        pass
                        # print("cursor.execute1")
                    except NameError as e:
                        pass
                        # print(e)

                    try:
                        #                         print("2")
                        #                         print(time.perf_counter())
                        #                         print("---------")
                        connection_for_data_and_variables.commit()
                    except psycopg2.DatabaseError as e:
                        pass
                        # print("connection.commit")
                    except AttributeError as e:
                        pass
                        # print(e)
                except psycopg2.InterfaceError as e:
                    if connection_for_data_and_variables: connection_for_data_and_variables.close()
                    connection_for_data_and_variables = None
                    # DB_switch_EXTERNAL_LOCAL()
                    Create_connection()
                    # Print_error("Insert step error", e)

                try:
                    try:
                        #                         print("3")
                        #                         print(time.perf_counter())
                        #                         print("---------")
                        cursor.execute('SELECT rt1, rt2, rt3, blr, allof, wifiid, wifipass FROM devicevariables \
                            WHERE sn=%s ORDER BY id DESC LIMIT 1;', (SN,))
                    except psycopg2.DatabaseError as e:
                        pass
                        # print("cursor.execute2")
                    except NameError as e:
                        pass
                        # print(e)
                    try:
                        #                         print("4")
                        #                         print(time.perf_counter())
                        #                         print("---------")
                        variables_list = cursor.fetchone()
                    except psycopg2.DatabaseError as e:
                        pass
                        # print("cursor.fetchone")
                    except NameError as e:
                        pass
                        # print(e)
                except psycopg2.InterfaceError as e:
                    if connection_for_data_and_variables: connection_for_data_and_variables.close()
                    connection_for_data_and_variables = None
                    # DB_switch_EXTERNAL_LOCAL()
                    Create_connection()
                    # Print_error("Select step error", e)

                # # 0-auto, 1-on, 2-off
                # if variables_list[0] in correct_variables:
                #     variable_RT1 = variables_list[0]
                # else:
                #     variable_RT1 = 2  # auto
                #
                # if variables_list[1] in correct_variables:
                #     variable_RT2 = variables_list[1]
                # else:
                #     variable_RT2 = 2  # auto
                #
                # if variables_list[2] in correct_variables:
                #     variable_RT3 = variables_list[2]
                # else:
                #     variable_RT3 = 2  # auto
                #
                # if variables_list[3] in correct_variables:
                #     variable_BLR = variables_list[3]
                # else:
                #     variable_BLR = 2  # on
                #
                # if variables_list[4] in correct_variables:
                #     variable_all_OFF = variables_list[4]
                # else:
                #     variable_all_OFF = 2  # auto

                variable_wifiid = variables_list[5]
                variable_wifipass = variables_list[6]

                if therm_bits > 0 or pump_bits > 0:

                    if (therm_bits & 1) == 1:
                        _numb = 1
                        _state = 1
                        _type = "thermostat"
                    elif (therm_bits & 10) == 2:
                        _numb = 1
                        _state = 0
                        _type = "thermostat"
                    elif (therm_bits & 100) == 4:
                        _numb = 2
                        _state = 1
                        _type = "thermostat"
                    elif (therm_bits & 1000) == 8:
                        _numb = 2
                        _state = 0
                        _type = "thermostat"
                    elif (therm_bits & 10000) == 16:
                        _numb = 3
                        _state = 1
                        _type = "thermostat"
                    elif (therm_bits & 100000) == 32:
                        _numb = 3
                        _state = 0
                        _type = "thermostat"
                    elif (pump_bits & 1) == 1:
                        _numb = 1
                        _state = 1
                        _type = "pump"
                    elif (pump_bits & 10) == 2:
                        _numb = 1
                        _state = 0
                        _type = "pump"
                    elif (pump_bits & 100) == 4:
                        _numb = 2
                        _state = 1
                        _type = "pump"
                    elif (pump_bits & 1000) == 8:
                        _numb = 2
                        _state = 0
                        _type = "pump"
                    elif (pump_bits & 10000) == 16:
                        _numb = 3
                        _state = 1
                        _type = "pump"
                    elif (pump_bits & 100000) == 32:
                        _numb = 3
                        _state = 0
                        _type = "pump"

                    timestamp = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())
                    data = [SN, timestamp, _type, _numb, _state]

                    try:
                        cursor.execute(
                            'INSERT INTO devicezonestatus (sn, time, type, rt, state) VALUES(%s,%s,%s,%s,%s);', data)
                        connection_for_data_and_variables.commit()

                        if _numb == 1 and _state == 1:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 0)
                            else:
                                pump_bits &= ~(1 << 0)
                        elif _numb == 1 and _state == 0:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 1)
                            else:
                                pump_bits &= ~(1 << 1)
                        elif _numb == 2 and _state == 1:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 2)
                            else:
                                pump_bits &= ~(1 << 2)
                        elif _numb == 2 and _state == 0:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 3)
                            else:
                                pump_bits &= ~(1 << 3)
                        elif _numb == 3 and _state == 1:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 4)
                            else:
                                pump_bits &= ~(1 << 4)
                        elif _numb == 3 and _state == 0:
                            if _type == "thermostat":
                                therm_bits &= ~(1 << 5)
                            else:
                                pump_bits &= ~(1 << 5)

                    except psycopg2.OperationalError as e:
                        pass

                # write_data_thread_status=0
                WIFI_LED_ON = 0
                watchdog = 0


#                 print("5")
#                 print(time.perf_counter())
#                 print("---------")


def Request_error_to_server():
    global server_host, server_dbname, server_username, server_password
    global write_error_thread_status, check_thread_status, error_sn, error_time, error_boilercurrent, error_ics1, error_ics2, error_ics3
    global error_t1, error_t2, error_t3, error_t4, error_t5, error_t6, error_t7, error_wt
    global error_relay1, error_relay2, error_relay3, error_relay4, error_relay5, error_relay6, error_relay7

    while True:

        if ((write_error_thread_status == 0) or (write_error_thread_status == 1)) and check_thread_status == 0:

            error_time = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())
            error_list = (
                error_sn, error_time, error_boilercurrent, error_ics1, error_ics2, error_ics3, error_t1, error_t2,
                error_t3,
                error_t4, error_t5, error_t6, error_t7, error_wt, error_relay1, error_relay2, error_relay3,
                error_relay4,
                error_relay5, error_relay6, error_relay7)

            try:
                connection_for_errors = psycopg2.connect(host=server_host, database=server_dbname, user=server_username,
                                                         password=server_password)
                cursor = connection_for_errors.cursor()
                cursor.execute('INSERT INTO \
                    devicetroubleshooting (sn, time, boilercurrent, ics1, ics2, ics3, \
                    t1, t2, t3, t4, t5, t6, t7, wt, relay1, relay2, relay3, relay4, relay5, relay6, relay7) \
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);', error_list)
                connection_for_errors.commit()
                write_error_thread_status = write_error_thread_status + 1
            except psycopg2.DatabaseError as e:
                pass
                # Print_error("Server DB to trouble error", e)
            finally:
                if connection_for_errors: connection_for_errors.close()


def Request_localDB():
    global to_db_status, data_time, data_sn, data_zone, data_boilerpumpfunamps, data_boiler, data_ics1, data_ics2, data_ics3, data_t1, data_t2
    global data_t3, data_t4, data_t5, data_t6, data_t7, data_ps, data_rt1, data_rt2, data_rt3, data_wt
    global db_start, counter, inner_db_data_list, inner_db_data_list_copy, main_db_data_list, from_db_status, retries, db_thread_status, check_thread_status, Quant

    connection_to_db = sqlite3.connect(local_dbname)
    cursor_to_db = connection_to_db.cursor()
    cursor_to_db_read = connection_to_db.cursor()

    while True:
        if db_thread_status == 1:

            if to_db_status == 1:

                data_time = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())

                sql = "INSERT INTO devicedata (sn,time,zone,boilerpumpfunamps,ics1,ics2,ics3,t1,t2,t3,t4,t5,t6,t7,ps,rt1,rt2,rt3,boiler,wt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                data = (data_sn, data_time, data_zone, data_boilerpumpfunamps, data_ics1, data_ics2, data_ics3, data_t1,
                        data_t2, data_t3, data_t4, data_t5, data_t6, data_t7, data_ps, data_rt1, data_rt2, data_rt3,
                        data_boiler, data_wt)
                #                 try:
                # print(data)
                cursor_to_db.execute(sql, data)
                connection_to_db.commit()
                #                 except Exception as e:
                #                     Print_error("Data_to_DB", e)

                if retries > 20:
                    to_db_status = 0
                    from_db_status = 1
                    check_thread_status = 0
                    retries = 0

            if from_db_status == 1:
                DB_check("cycle")
                try:
                    text = "SELECT sn,time,zone,boilerpumpfunamps,ics1,ics2,ics3,t1,t2,t3,t4,t5,t6,t7,ps,rt1,rt2,rt3,boiler FROM devicedata WHERE rowID>=" + str(
                        Quant)
                    cursor_to_db_read.execute(text)
                except Exception as e:
                    pass
                    # Print_error("Data_from_DB_1", e)
                try:
                    res = cursor_to_db_read.fetchall()

                    try:
                        connection_to_server_db = psycopg2.connect(host=server_host, database=server_dbname,
                                                                   user=server_username, password=server_password)
                        cursor_to_server_db = connection_to_server_db.cursor()

                        for row in res:
                            inner_db_data_list[0] = SN
                            inner_db_data_list[1] = row[0]
                            inner_db_data_list[2] = TZ
                            inner_db_data_list[3] = row[1]
                            inner_db_data_list[4] = row[2]
                            inner_db_data_list[5] = row[3]
                            inner_db_data_list[6] = row[4]
                            inner_db_data_list[7] = row[5]
                            inner_db_data_list[8] = row[6]
                            inner_db_data_list[9] = row[7]
                            inner_db_data_list[10] = row[8]
                            inner_db_data_list[11] = row[9]
                            inner_db_data_list[12] = row[10]
                            inner_db_data_list[13] = row[11]
                            inner_db_data_list[14] = row[12]
                            inner_db_data_list[15] = row[13]
                            inner_db_data_list[16] = row[14]
                            inner_db_data_list[17] = row[15]
                            inner_db_data_list[18] = row[16]
                            inner_db_data_list[19] = row[17]
                            inner_db_data_list[20] = row[18]
                            inner_db_data_list_copy = inner_db_data_list.copy()
                            # main_db_data_list.append(inner_db_data_list_copy)

                            cursor_to_server_db.execute('INSERT INTO \
                                data (sn, time, zone, ecs1, ecs2, ics1, ics2, ics3, \
                                t1, t2, t3, t4, t5, t6, t7, ps, rt1, rt2, rt3, ws, wt) \
                                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);',
                                                        tuple(inner_db_data_list_copy))
                            # print(tuple(inner_db_data_list_copy))
                        connection_to_server_db.commit()

                        i = 0
                        while i != 2:
                            pass
                            # print(i)
                            # i=DB_clear()

                        main_db_data_list.clear()
                        from_db_status = 0

                    except psycopg2.DatabaseError as e:
                        pass
                        # Print_error("Post_DB_Data", e)
                        to_db_status = 1
                        from_db_status = 0
                        check_thread_status = 1
                        main_db_data_list.clear()
                        retries = 0
                        WIFI_LED_ON = 1
                    finally:
                        if connection_to_server_db: connection_to_server_db.close()

                except Exception as e:
                    pass
                    # Print_error("Data_from_DB_2", e)
                    # time_stamp=inner_db_data_list[1]
                # inner_db_data_list[1]=(datetime.strptime(time_stamp,"%m/%d/%Y %H:%M:%S")+timedelta(seconds=1)).strftime("%m/%d/%Y %H:%M:%S")
                # inner_db_data_list_copy=inner_db_data_list.copy()
                # main_db_data_list.append(inner_db_data_list_copy)
                # print(main_db_data_list)
                # inner_db_data_list[1]=(datetime.strptime(time_stamp,"%m/%d/%Y %H:%M:%S")+timedelta(seconds=2)).strftime("%m/%d/%Y %H:%M:%S")
                # inner_db_data_list_copy=inner_db_data_list.copy()
                # main_db_data_list.append(inner_db_data_list_copy)

            db_thread_status = 0


def Check_connection():
    global server_host, server_dbname, server_username, server_password
    global retries, check_thread_status, watchdog
    while True:

        if check_thread_status == 1:

            try:
                check_connection = psycopg2.connect(host=server_host, database=server_dbname, user=server_username,
                                                    password=server_password, connect_timeout=2)
            except psycopg2.OperationalError as e:
                retries = 0
            try:
                if check_connection:
                    check_connection.close()
                    retries = retries + 1
            except psycopg2.OperationalError as e:
                retries = 0
            except UnboundLocalError as e:
                retries = 0

        if watchdog > 10:
            os.system(cmd)




def IO_update():
    global data_rt1, data_rt2, data_rt3, variables_list, variables_list_old, variable_all_OFF, variable_RT1, variable_RT2, variable_RT3, variable_BLR, bias, last_bias, therm_bits, pump_bits, data_end, reset_temp_repeat


    if variables_list[4] in range(2, 9, 3):  # all outputs in auto/manual mode
        bias = 16

    #if variables_list_old[3] != variables_list[3] or variables_list_old[0] != variables_list[0] or variables_list_old[1] != variables_list[1] or variables_list_old[2] != variables_list[2]:
        # if (variables_list[3] in range(2, 9, 3)) and (GPIO.input(therm1_stat) == GPIO.HIGH or GPIO.input(therm2_stat) == GPIO.HIGH or GPIO.input(therm3_stat) == GPIO.HIGH):
        if (variables_list[3] in range(2, 9, 3)) and (GPIO.input(pump_ctrl1) == 1 or GPIO.input(pump_ctrl2) == 1 or GPIO.input(pump_ctrl3) == 1):
            GPIO.output(endswitch_ctrl, GPIO.HIGH)
            data_end = 1
            bias |= (1 << 0)
        # if (variables_list[3] in range(2, 9, 3)) and (GPIO.input(therm1_stat) == GPIO.LOW) and (GPIO.input(therm2_stat) == GPIO.LOW) and (GPIO.input(therm3_stat) == GPIO.LOW):
        if (variables_list[3] in range(2, 9, 3)) and (GPIO.input(pump_ctrl1) == 0) and (GPIO.input(pump_ctrl2) == 0) and (GPIO.input(pump_ctrl3) == 0):
            GPIO.output(endswitch_ctrl, GPIO.LOW)
            data_end = 0
            bias &= ~(1 << 0)
        if (variables_list[3] in range(1, 9, 3)):
            GPIO.output(endswitch_ctrl, GPIO.HIGH)
            data_end = 1
            bias |= (1 << 0)
        if (variables_list[3] in range(0, 9, 3)):
            GPIO.output(endswitch_ctrl, GPIO.LOW)
            data_end = 0
            bias &= ~(1 << 0)
       #variables_list_old[3] = variables_list[3]


        if variables_list_old[0] != variables_list[0]:
            if (variables_list[0] in range(2, 9, 3)) and (GPIO.input(therm1_stat) == GPIO.HIGH):
                GPIO.output(pump_ctrl1, GPIO.HIGH)
                pump_bits |= (1 << 0)
                bias |= (1 << 3)
            if (variables_list[0] in range(2, 9, 3)) and (GPIO.input(therm1_stat) == GPIO.LOW):
                GPIO.output(pump_ctrl1, GPIO.LOW)
                pump_bits |= (1 << 1)
                bias &= ~(1 << 3)
            if (variables_list[0] in range(1, 9, 3)):
                GPIO.output(pump_ctrl1, GPIO.HIGH)
                pump_bits |= (1 << 0)
                bias |= (1 << 3)
            if (variables_list[0] in range(0, 9, 3)):
                GPIO.output(pump_ctrl1, GPIO.LOW)
                pump_bits |= (1 << 1)
                bias &= ~(1 << 3)
            variables_list_old[0] = variables_list[0]

        if variables_list_old[1] != variables_list[1]:
            if (variables_list[1] in range(2, 9, 3)) and (GPIO.input(therm2_stat) == GPIO.HIGH):
                GPIO.output(pump_ctrl2, GPIO.HIGH)
                pump_bits |= (1 << 2)
                bias |= (1 << 2)
            if (variables_list[1] in range(2, 9, 3)) and (GPIO.input(therm2_stat) == GPIO.LOW):
                GPIO.output(pump_ctrl2, GPIO.LOW)
                pump_bits |= (1 << 3)
                bias &= ~(1 << 2)
            if (variables_list[1] in range(1, 9, 3)):
                GPIO.output(pump_ctrl2, GPIO.HIGH)
                pump_bits |= (1 << 2)
                bias |= (1 << 2)
            if (variables_list[1] in range(0, 9, 3)):
                GPIO.output(pump_ctrl2, GPIO.LOW)
                pump_bits |= (1 << 3)
                bias &= ~(1 << 2)
            variables_list_old[1] = variables_list[1]

        if variables_list_old[2] != variables_list[2]:
            if (variables_list[2] in range(2, 9, 3)) and (GPIO.input(therm3_stat) == GPIO.HIGH):
                GPIO.output(pump_ctrl3, GPIO.HIGH)
                pump_bits |= (1 << 4)
                bias |= (1 << 1)
            if (variables_list[2] in range(2, 9, 3)) and (GPIO.input(therm3_stat) == GPIO.LOW):
                GPIO.output(pump_ctrl3, GPIO.LOW)
                pump_bits |= (1 << 5)
                bias &= ~(1 << 1)
            if (variables_list[2] in range(1, 9, 3)):
                GPIO.output(pump_ctrl3, GPIO.HIGH)
                pump_bits |= (1 << 4)
                bias |= (1 << 1)
            if (variables_list[2] in range(0, 9, 3)):
                GPIO.output(pump_ctrl3, GPIO.LOW)
                pump_bits |= (1 << 5)
                bias &= ~(1 << 1)
            variables_list_old[2] = variables_list[2]



    if variables_list_old[4] != variables_list[4]:
        if variables_list[4] in range(1, 9, 3):  # all outputs ON
            GPIO.output(pump_ctrl1, GPIO.HIGH)
            pump_bits |= (1 << 0)
            GPIO.output(pump_ctrl2, GPIO.HIGH)
            pump_bits |= (1 << 2)
            GPIO.output(pump_ctrl3, GPIO.HIGH)
            pump_bits |= (1 << 4)
            GPIO.output(endswitch_ctrl, GPIO.HIGH)
            bias = 31

        if variables_list[4] in range(0, 9, 3):  # all outputs OFF
            GPIO.output(pump_ctrl1, GPIO.LOW)
            pump_bits |= (1 << 1)
            GPIO.output(pump_ctrl2, GPIO.LOW)
            pump_bits |= (1 << 3)
            GPIO.output(pump_ctrl3, GPIO.LOW)
            pump_bits |= (1 << 5)
            GPIO.output(endswitch_ctrl, GPIO.LOW)
            bias = 16
        variables_list_old[4] = variables_list[4]

    if data_rt1 == 0 and (GPIO.input(therm1_stat) == GPIO.HIGH):
        data_rt1 = 1
        therm_bits |= (1 << 0)
    if data_rt1 == 1 and (GPIO.input(therm1_stat) == GPIO.LOW):
        data_rt1 = 0
        therm_bits |= (1 << 1)

    if data_rt2 == 0 and GPIO.input(therm2_stat) == GPIO.HIGH:
        data_rt2 = 1
        therm_bits |= (1 << 2)
    if data_rt2 == 1 and GPIO.input(therm2_stat) == GPIO.LOW:
        data_rt2 = 0
        therm_bits |= (1 << 3)

    if data_rt3 == 0 and GPIO.input(therm3_stat) == GPIO.HIGH:
        data_rt3 = 1
        therm_bits |= (1 << 4)
    if data_rt3 == 1 and GPIO.input(therm3_stat) == GPIO.LOW:
        data_rt3 = 0
        therm_bits |= (1 << 5)

    if GPIO.input(reset_temp) == GPIO.HIGH:
        reset_temp_repeat += 1
    else:
        reset_temp_repeat = 0

    if reset_temp_repeat > 5:
        if os.path.exists("/home/pi/sensorsID.txt"):
            os.system('rm /home/pi/sensorsID.txt')
            os.system(cmd)

    if last_bias != bias:
        try:
            tmp = bus.read_i2c_block_data(address, bias)
            last_bias = bias
        except BaseException:
            pass
            # print("bias error")


def Reset_WiFi():
    global connection_for_data_and_variables, cursor, set_WiFi, variables_list
    global variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF, variable_wifiid, variable_wifipass

    variable_wifipass = "0"
    data_list = [SN, variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF, variable_wifiid,
                 variable_wifipass]
    variables_list = data_list

    print("start WiFi-connect")
    os.system('sudo wifi-connect')

    cursor.execute(
        'INSERT INTO devicevariables (sn, rt1, rt2, rt3, blr, allof, wifiid, wifipass) VALUES(%s,%s,%s,%s,%s,%s,%s,%s);',
        data_list)
    connection_for_data_and_variables.commit()

    set_WiFi = 0

    time.sleep(3)

    GPIO.output(pin_LED_WiFi, GPIO.LOW)


def Update_source():
    global connection_for_data_and_variables, cursor, set_WiFi, variables_list
    global variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF, variable_wifiid, variable_wifipass

    variable_wifiid = "0"
    variable_wifipass = "0"
    data_list = [SN, variable_RT1, variable_RT2, variable_RT3, variable_BLR, variable_all_OFF, variable_wifiid,
                 variable_wifipass]
    variables_list = data_list

    cursor.execute(
        'INSERT INTO devicevariables (sn, rt1, rt2, rt3, blr, allof, wifiid, wifipass) VALUES(%s,%s,%s,%s,%s,%s,%s,%s);',
        data_list)
    connection_for_data_and_variables.commit()

    os.system(
        'curl -L https://raw.githubusercontent.com/AlexShten/NYC_project/main/SQUID_MAIN_V1.py -o /home/pi/GitHub_source/SQUID_MAIN_V1.py')
    os.system(cmd)


# ----------------------------------------------------------------------------------------------------

def Read_ADCs():
    global data_boilerpumpfunamps, data_boiler, data_ics1, data_ics2, data_ics3, data_ps, adc, address, bus

    while True:
        if adc == 1:

            try:
                tmp = bus.read_i2c_block_data(address, 1)  # read channel 1 from arduino
                number = (tmp[0] + tmp[1] * 256) / 1000
                data_ics1 = round(number, 2)
            except BaseException:
                pass
                # print("data_pump1 error")

            try:
                tmp = bus.read_i2c_block_data(address, 2)  # read channel 2 from arduino
                number = (tmp[0] + tmp[1] * 256) / 1000
                data_ics2 = round(number, 2)
            except BaseException:
                pass
                # print("data_pump2 error")

            try:
                tmp = bus.read_i2c_block_data(address, 3)  # read channel 3 from arduino
                number = (tmp[0] + tmp[1] * 256) / 1000
                data_ics3 = round(number, 2)
            except BaseException:
                pass
                # print("data_pump3 error")

            try:
                tmp = bus.read_i2c_block_data(address, 4)  # read channel 4 from arduino
                number = (tmp[0] + tmp[1] * 256) / 1000
                data_boiler = round(number, 2)
            except BaseException:
                pass
                # print("data_boiler error")

            try:
                tmp = bus.read_i2c_block_data(address, 5)  # read channel 5 from arduino
                number = (tmp[0] + tmp[1] * 256) / 1000
                data_boilerpumpfunamps = round(number, 2)
            except BaseException:
                pass
                # print("data_common error")

            try:
                tmp = bus.read_i2c_block_data(address, 6)  # read channel 6 from arduino
                number = (tmp[0] + tmp[1] * 256) * 0.17
                data_ps = round(number, 2)
            except BaseException:
                pass
                # print("data_PS error")

            adc = 0


# def Update_sens():


def Search_sens():
    global sensors_in_system, quantity_temp_sens, path_to_file

    i = 0
    if os.path.exists(path_to_file):
        with open(path_to_file, "r") as file:
            for line in file:
                sensors_in_system[i] = line.replace('\n', '')
                i = i + 1
    else:
        try:
            for sensor in W1ThermSensor.get_available_sensors():  # [W1ThermSensor.THERM_SENSOR_DS18B20]):
                available_sensors[i] = sensor.id
                # os.system("sudo su")
                # sensor.set_resolution(10, persist=True)
                i = i + 1
        except BaseException as e:
            pass
            # print(e)

        equality = 0
        for step1 in range(quantity_temp_sens):
            if available_sensors[step1] != None:
                equality = 0
                for step2 in range(quantity_temp_sens):
                    if sensors_in_system[step2] == available_sensors[step1]:
                        equality = 1
                        break
                if equality == 0:
                    for step2 in range(quantity_temp_sens):
                        if sensors_in_system[step2] == None:
                            sensors_in_system[step2] = copy.deepcopy(available_sensors[step1])
                            break
            else:
                continue

        i = 0
        for step3 in range(quantity_temp_sens):
            if sensors_in_system[step3] == None:
                i = i + 1
        if i == 0:
            try:
                write_in_file = open(path_to_file, "w")
                try:
                    for step4 in range(quantity_temp_sens):
                        write_in_file.write(sensors_in_system[step4] + "\n")
                except Exception as e:
                    pass
                    # Print_error("Write to file", e)
                finally:
                    write_in_file.close()
            except Exception as ex:
                pass
                # Print_error("Open file", ex)


def Read_temps():
    global write_error_thread_status, sensors_in_system, weather_timer
    global data_t1, error_t1, data_t2, error_t2, data_t3, error_t3, data_t4, error_t4, data_t5, error_t5, data_t6, error_t6, data_t7, error_t7, data_wt
    sensor1_error = 1
    sensor2_error = 1
    sensor3_error = 1
    sensor4_error = 1
    sensor5_error = 1
    sensor6_error = 1
    sensor7_error = 1
    sensor1_ready = False
    sensor2_ready = False
    sensor3_ready = False
    sensor4_ready = False
    sensor5_ready = False
    sensor6_ready = False
    sensor7_ready = False
    while True:

        if sensors_in_system[0] != None and sensor1_ready == False:
            try:
                sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[0])
                sensor1_ready = True
            except Exception as e:
                pass
                # Print_error("sens1", e)

        if sensor1_ready == True:
            try:
                data_t1 = (sensor1.get_temperature()) * 1.8 + 32
                if sensor1_error == 0:
                    error_t1 = 0
                    sensor1_error = 1
                    write_error_thread_status = 0
                # print("S1 - %s" % sensor1.get_temperature())
            except BaseException:
                if sensor1_error == 1:
                    error_t1 = 1
                    sensor1_error = 0
                    write_error_thread_status = 0
                    data_t1 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[0])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[1] != None and sensor2_ready == False:
            try:
                sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[1])
                sensor2_ready = True
            except Exception as e:
                pass
                # Print_error("sens2", e)

        if sensor2_ready == True:
            try:
                data_t2 = (sensor2.get_temperature()) * 1.8 + 32
                if sensor2_error == 0:
                    error_t2 = 0
                    sensor2_error = 1
                    write_error_thread_status = 0
                # print("S2 - %s" % sensor2.get_temperature())
            except BaseException:
                if sensor2_error == 1:
                    error_t2 = 1
                    sensor2_error = 0
                    write_error_thread_status = 0
                    data_t2 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[1])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[2] != None and sensor3_ready == False:
            try:
                sensor3 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[2])
                sensor3_ready = True
            except Exception as e:
                pass
                # Print_error("sens3", e)

        if sensor3_ready == True:
            try:
                data_t3 = (sensor3.get_temperature()) * 1.8 + 32
                if sensor3_error == 0:
                    error_t3 = 0
                    sensor3_error = 1
                    write_error_thread_status = 0
                # print("S3 - %s" % data_t3)
            except BaseException:
                if sensor3_error == 1:
                    error_t3 = 1
                    sensor3_error = 0
                    write_error_thread_status = 0
                    data_t3 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[2])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[3] != None and sensor4_ready == False:
            try:
                sensor4 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[3])
                sensor4_ready = True
            except Exception as e:
                pass
                # Print_error("sens4", e)

        if sensor4_ready == True:
            try:
                data_t4 = (sensor4.get_temperature()) * 1.8 + 32
                if sensor4_error == 0:
                    error_t4 = 0
                    sensor4_error = 1
                    write_error_thread_status = 0
                # print("S4 - %s" % data_t4)
            except BaseException:
                if sensor4_error == 1:
                    error_t4 = 1
                    sensor4_error = 0
                    write_error_thread_status = 0
                    data_t4 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[3])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[4] != None and sensor5_ready == False:
            try:
                sensor5 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[4])
                sensor5_ready = True
            except Exception as e:
                pass
                # Print_error("sens5", e)

        if sensor5_ready == True:
            try:
                data_t5 = (sensor5.get_temperature()) * 1.8 + 32
                if sensor5_error == 0:
                    error_t5 = 0
                    sensor5_error = 1
                    write_error_thread_status = 0
                # print("S5 - %s" % data_t5)
            except BaseException:
                if sensor5_error == 1:
                    error_t5 = 1
                    sensor5_error = 0
                    write_error_thread_status = 0
                    data_t5 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[4])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[5] != None and sensor6_ready == False:
            try:
                sensor6 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[5])
                sensor6_ready = True
            except Exception as e:
                pass
                # Print_error("sens6", e)

        if sensor6_ready == True:
            try:
                data_t6 = (sensor6.get_temperature()) * 1.8 + 32
                if sensor6_error == 0:
                    error_t6 = 0
                    sensor6_error = 1
                    write_error_thread_status = 0
                # print("S6 - %s" % data_t6)
            except BaseException:
                if sensor6_error == 1:
                    error_t6 = 1
                    sensor6_error = 0
                    write_error_thread_status = 0
                    data_t6 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[5])
        # ------------------------------------------------------------------------------------------------
        if sensors_in_system[6] != None and sensor7_ready == False:
            try:
                sensor7 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensors_in_system[6])
                sensor7_ready = True
            except Exception as e:
                pass
                # Print_error("sens7", e)

        if sensor7_ready == True:
            try:
                data_t7 = (sensor7.get_temperature()) * 1.8 + 32
                if sensor7_error == 0:
                    error_t7 = 0
                    sensor7_error = 1
                    write_error_thread_status = 0
                # print("S7 - %s" % data_t7)
            except BaseException:
                if sensor7_error == 1:
                    error_t7 = 1
                    sensor7_error = 0
                    write_error_thread_status = 0
                    data_t7 = None
                pass
                # print("Sensor %s not available" % sensors_in_system[6])

        if weather_timer >= 1800:
            try:
                owm = OWM('4c4f23e81d10a949967cf9a7223182e1')
                mgr = owm.weather_manager()
                observation = mgr.weather_at_place("New Paltz,US")
                w = observation.weather
                data_wt = w.temperature('fahrenheit')['temp']
            except BaseException as e:
                pass
                # print(e)
            weather_timer = 0


# def DB_clear():
#     i=0
#     try:
#         cursor_to_db_clear.execute("DELETE QUICK FROM devicedata where rowID>0;")
#         i=i+1
#     except Exception as e:
#         Print_error("DB_clear_1", e)
#     try:    
#         cursor_to_db_clear.execute("ALTER TABLE devicedata AUTO_INCREMENT=0;")
#         i=i+1
#     except Exception as e:
#         Print_error("DB_clear_2", e)
#     return i
# 
# def DB_check(call):
#     global to_db_status, from_db_status, Quant
#     try:
#         cursor_to_db.execute("SELECT COUNT(*) FROM devicedata;")
#     except Exception as e:
#         Print_error("Read quant in DB", e)
#     try:    
#         vol=cursor_to_db.fetchone()
#         if vol[0]>0:
#             if call=="start":
#                 to_db_status=0
#                 from_db_status=1
#             else:    
#                 if vol[0]>numbers:
#                     Quant=vol[0]-numbers
#                 else:
#                     Quant=0
#     except Exception as e:
#         Print_error("Control quant in DB", e)

def LED_blink(status):
    global var
    if status == 0:
        GPIO.output(pin_LED_WiFi, GPIO.LOW)

    if status == 1:
        if var == 0:
            GPIO.output(pin_LED_WiFi, GPIO.HIGH)
            var = 1

        else:
            GPIO.output(pin_LED_WiFi, GPIO.LOW)
            #             os.system("clear")
            var = 0


def Init_WiFi():
    global wifi_recconnect_flag, wifi_recconnect_repeat

    wifi_recconnect_flag = 1
    try:
        file = open("/home/pi/wifi_recconnect.txt", "r")
        wifi_recconnect_repeat = int(file.read())
        file.close()
    except:
        wifi_recconnect_repeat = 4

    if os.popen('iwgetid -r').read() == "":
        print("start WiFi-connect")
        os.system('sudo wifi-connect')

    try:
        file = open("/home/pi/wifi_recconnect.txt", "w")
        file.write("0")
        file.close()
    except:
        pass

    wifi_recconnect_flag = 0


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.cleanup()

pin_LED_User = 17
pin_LED_WiFi = 18
pin_LED_Power = 27

GPIO.setup(pin_LED_User, GPIO.OUT)
GPIO.setup(pin_LED_WiFi, GPIO.OUT)
# GPIO.setup(pin_LED_Power, GPIO.OUT)
GPIO.output(pin_LED_User, GPIO.LOW)
GPIO.output(pin_LED_WiFi, GPIO.LOW)
# GPIO.output(pin_LED_Power, GPIO.HIGH)

pump_ctrl1 = 13
pump_ctrl2 = 5
pump_ctrl3 = 1
endswitch_ctrl = 0

GPIO.setup(pump_ctrl1, GPIO.OUT)
GPIO.setup(pump_ctrl2, GPIO.OUT)
GPIO.setup(pump_ctrl3, GPIO.OUT)
GPIO.setup(endswitch_ctrl, GPIO.OUT)
GPIO.output(pump_ctrl1, GPIO.LOW)
GPIO.output(pump_ctrl2, GPIO.LOW)
GPIO.output(pump_ctrl3, GPIO.LOW)
GPIO.output(endswitch_ctrl, GPIO.LOW)

therm1_stat = 16
therm2_stat = 19
therm3_stat = 20
bypass_stat = 26

reset_temp = 12

GPIO.setup(therm1_stat, GPIO.IN)
GPIO.setup(therm2_stat, GPIO.IN)
GPIO.setup(therm3_stat, GPIO.IN)
GPIO.setup(bypass_stat, GPIO.IN)
GPIO.setup(reset_temp, GPIO.IN)

Search_sens()

bus = smbus.SMBus(1)
address = 3

call_System_tick_1_sec = threading.Thread(target=System_tick_1_sec, args=(), daemon=True)
call_System_tick_05_sec = threading.Thread(target=System_tick_05_sec, args=(), daemon=True)

call_Check_connection = threading.Thread(target=Check_connection, args=(), daemon=True)
call_Init_WiFi = threading.Thread(target=Init_WiFi, args=(), daemon=True)

call_Request_data_to_server = threading.Thread(target=Request_data_to_server, args=(), daemon=True)
call_Request_localDB = threading.Thread(target=Request_localDB, args=(), daemon=True)

call_Read_ADCs = threading.Thread(target=Read_ADCs, args=(), daemon=True)
call_Read_temps = threading.Thread(target=Read_temps, args=(), daemon=True)

if __name__ == "__main__":

    time.sleep(15)

    # Init_WiFi()
    call_Init_WiFi.start()

    call_System_tick_1_sec.start()
    call_System_tick_05_sec.start()

    call_Read_ADCs.start()
    call_Read_temps.start()

    # DB_clear()
    # DB_check("start")
    IO_update()

    # call_Request_localDB.start()
    time.sleep(1)
    call_Check_connection.start()
    check_thread_status = 1
    time.sleep(1)
    call_Request_data_to_server.start()

    while True:
        if main == 1:

            IO_update()

            if wait_wifi > wait_times[wifi_recconnect_repeat]:

                wifi_recconnect_repeat += 1

                if wifi_recconnect_repeat > 4:
                    wifi_recconnect_repeat = 4

                try:
                    file = open("/home/pi/wifi_recconnect.txt", "w")
                    file.write(str(wifi_recconnect_repeat))
                    file.close()
                except:
                    pass

                os.system(cmd)

            if variable_wifipass == "1" and variable_wifiid == "0":
                GPIO.output(pin_LED_WiFi, GPIO.HIGH)
                set_WiFi = 1

                time.sleep(3)
                Reset_WiFi()

            if variable_wifipass == "1" and variable_wifiid == "1":
                update = 1

                time.sleep(3)
                Update_source()

            # ---------------------------???????????????How to replace sensor???????
            for i in range(quantity_temp_sens):
                if sensors_in_system[i] == None:
                    Search_sens()

            if call_System_tick_1_sec.is_alive() == False:
                restart = 1
            if call_System_tick_05_sec.is_alive() == False:
                restart = 1
            if call_Request_data_to_server.is_alive() == False:
                restart = 1
            # if call_Request_localDB.is_alive() == False:
            #     restart = 1
            if call_Check_connection.is_alive() == False:
                restart = 1
            if call_Read_ADCs.is_alive() == False:
                restart = 1
            if call_Read_temps.is_alive() == False:
                restart = 1
            if restart == 1:
                os.system(cmd)

            main = 0

        if led == 1:
            LED_blink(WIFI_LED_ON)

            led = 0
