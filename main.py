from machine import Pin, PWM, ADC
import time


# ------------------------- Configuracion de pines-----------

# Servos
servo_base = PWM(Pin(13), freq=50)
servo_brazo = PWM(Pin(12), freq=50)

# Potenciómetros
pot_base = ADC(Pin(34))
pot_brazo = ADC(Pin(32))

pot_base.atten(ADC.ATTN_11DB)
pot_brazo.atten(ADC.ATTN_11DB)

# LEDs
led_manual = Pin(27, Pin.OUT)
led_auto = Pin(4, Pin.OUT)

# Buzzer (Para emitir sonido)
buzzer = PWM(Pin(5))
buzzer.duty(0) #0 porque inicia apagado

# Botones PULL_UP: normalmente están en HIGH
btn_reset = Pin(0, Pin.IN, Pin.PULL_UP) 
btn_auto = Pin(16, Pin.IN, Pin.PULL_UP)


# ------------------------------Variables  ---------------------

estado = "MANUAL"
ultimo_evento = 0
DEBOUNCE = 200 #0.2ms

pos_base = 90
pos_brazo = 0


# ------------------------------ Funciones ------------------------------

def angulo_a_duty(angulo): #convierte el valor nmerico de us a PWM (0-65535)
    return int((angulo / 180 * 2000 + 500) * 65535 / 20000)

def mover(servo, angulo): #mover el servomotor
    servo.duty_u16(angulo_a_duty(angulo))

def mover_suave(servo, actual, destino, paso=2): # mov progresivos entre dos posiciones angulares
    if actual < destino:
        rango = range(actual, destino, paso)
    else:
        rango = range(actual, destino, -paso)

    for i in rango:
        mover(servo, i)
        time.sleep(0.02)

    mover(servo, destino)
    return destino

def leer_pots(): #Convierte lectura (0–4095) a grados (0–180)
    base = int(pot_base.read() * 180 / 4095)
    brazo = int(pot_brazo.read() * 180 / 4095)
    return base, brazo

def alarma(on):
    if on:
        led_auto.on()
        buzzer.freq(1000) 
        buzzer.duty(300) # Intensidad de volumen
    else:
        led_auto.off()
        buzzer.duty(0) 


# ----------------Interrupciones ------------

def irq_reset(pin):
    global estado, ultimo_evento
    t = time.ticks_ms()
    if time.ticks_diff(t, ultimo_evento) > DEBOUNCE:
        estado = "RETORNO"
        ultimo_evento = t

def irq_auto(pin):
    global estado, ultimo_evento
    t = time.ticks_ms()
    if time.ticks_diff(t, ultimo_evento) > DEBOUNCE:
        estado = "SECUENCIA"
        ultimo_evento = t

btn_reset.irq(trigger=Pin.IRQ_FALLING, handler=irq_reset) # Activa la interrupción en flanco de bajada
btn_auto.irq(trigger=Pin.IRQ_FALLING, handler=irq_auto)



# ----------------------------------- MODOS ----------------------------------

def modo_manual():
    global pos_base, pos_brazo
    
    led_manual.on()
    alarma(False)
    #El sistema detecta que movió el potenciómetro porque cambia el valor leído por el ADC
    b, br = leer_pots()
    
    mover(servo_base, b)
    mover(servo_brazo, br)
    
    pos_base = b
    pos_brazo = br

def modo_retorno():
    global pos_base, pos_brazo, estado
    
    led_manual.off()
    alarma(True)

    pos_base = mover_suave(servo_base, pos_base, 0)
    pos_brazo = mover_suave(servo_brazo, pos_brazo, 0)

    alarma(False)
    estado = "ESPERA"

def modo_secuencia():
    global pos_base, pos_brazo, estado
    
    led_manual.off()
    alarma(True)
    
    #Guarda la posicion en la que estaba, para que e usuaria no pierda el control.
    base_ini = pos_base
    brazo_ini = pos_brazo

    # Secuencia distinta
    movimientos = [
        (30, 60),
        (150, 120),
        (90, 30),
        (180, 150),
        (0, 0)
    ]

    for b, br in movimientos:
        pos_base = mover_suave(servo_base, pos_base, b)
        pos_brazo = mover_suave(servo_brazo, pos_brazo, br)

    # Regresar a posición inicial
    pos_base = mover_suave(servo_base, pos_base, base_ini)
    pos_brazo = mover_suave(servo_brazo, pos_brazo, brazo_ini)

    alarma(False)
    estado = "MANUAL"

def modo_espera():
    global estado
    
    led_manual.on()
    
    b, br = leer_pots()
    
    # Tolerancia mayor (mejor UX)
    if b < 15 and br < 15:
        estado = "MANUAL"


#----------- LOOP PRINCIPAL -------------------

print("Sistema listo")

while True:

    if estado == "MANUAL":
        modo_manual()

    elif estado == "RETORNO":
        modo_retorno()

    elif estado == "SECUENCIA":
        modo_secuencia()

    elif estado == "ESPERA":
        modo_espera()

    time.sleep(0.05) #Pausa para no saturar el CPU
