from __future__ import division
import hashlib
import hmac
import base64
import urlparse
import ConfigParser
import simplejson
import urllib2
import time
import datetime
from math import cos, sin, tan, sqrt, pi, radians, degrees, asin, atan2


def build_url(origin='',
              destination='',
              access_type='personal',
              config_path='config/'):
    """
    Determinar la url para la busqueda deseada.
    Esto puede resultar complicado si se usa la versión paga de Google Maps (Google Maps para Negocios).
    """
    # El origen puede ser una dirección en cadena (como '1 N State St Chicago IL') o estar en [lat, lng]
    if origin == '':
        raise Exception('el origen no puede estar en blanco.')
    elif isinstance(origin, str):
        origin_str = origin.replace(' ', '+')
    elif isinstance(origin, list) and len(origin) == 2:
        origin_str = ','.join(map(str, origin))
    else:
        raise Exception('el origen debe ser una lista [lat, lng] o una dirección en cadena.')
    # El destino también debe ser una cadena o ser una lista de [lat, lng] pero es generado de maner automática
    if destination == '':
        raise Exception('el destino no puede estar en blanco.')
    elif isinstance(destination, str):
        destination_str = destination.replace(' ', '+')
    elif isinstance(destination, list):
        destination_str = ''
        for element in destination:
            if isinstance(element, str):
                destination_str = '{0}|{1}'.format(destination_str, element.replace(' ', '+'))
            elif isinstance(element, list) and len(element) == 2:
                destination_str = '{0}|{1}'.format(destination_str, ','.join(map(str, element)))
            else:
                raise Exception('el destino debe ser una lista de [lat, lng] o una lista de direciones.')
        destination_str = destination_str.strip('|')
    else:
        raise Exception('el destino debe ser una lista de [lat, lng] o una lista de cadenas.')
    # El tipo de acceso es o 'personal' o de 'negocios'
    if access_type not in ['personal', 'business']:
        raise Exception("el tipo de acceso puede ser 'personal' o de 'negocios'.")

    # Obtener la llave de la API de Google desde un archivo externo de .config
    # Si se esta usando Business Google Maps (debido al número de consultas),
    # este archivo debe tener el siguiente formato:
    #
    # [api]
    # client_id=<your client id>
    # crypto_key=<your crypto key>
    #
    # Si se esta usando la versión personal de Google Maps, el formato debe ser:
    #
    # [api]
    # api_number=<your api number>
    #
    config = ConfigParser.SafeConfigParser()
    config.read('{}google_maps.cfg'.format(config_path))
    if access_type == 'personal':
        key = config.get('api', 'api_number')
    if access_type == 'business':
        client = config.get('api', 'client_id')

    # Si se esta usando Business Google Maps, el cálculo usará las condiciones de tráfico actuales
    departure = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1, 0, 0, 0)

    # Convertimos la cadena en una URL, que podamos usar
    # usamos la función urlparse() en la consulta
    # Esta URL ya debe estar codificada correctamente
    prefix = 'https://maps.googleapis.com/maps/api/distancematrix/json?mode=transit&units=metric&avoid=tolls|ferries'
    if access_type == 'personal':
        url = urlparse.urlparse('{0}&origins={1}&destinations={2}&key={3}'.format(prefix,
                                                                                  origin_str,
                                                                                  destination_str,
                                                                                  key))
        full_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query
        return full_url
    if access_type == 'business':
        url = urlparse.urlparse('{0}&origins={1}&destinations={2}&departure_time={3}&client={4}'.format(prefix,
                                                                                                        origin_str,
                                                                                                        destination_str,
                                                                                                        int(departure.total_seconds()),
                                                                                                        client))
        # Obtener la private_key usada al solicitar la API
        private_key = config.get('api', 'crypto_key')
        # Requerimos juntar el camino y la consulta como parte de la cadena
        url_to_sign = url.path + "?" + url.query
        # Decodificar la private key a su forma binaria
        decoded_key = base64.urlsafe_b64decode(private_key)
        # Crear a una firma usando la llave y la URL-codificada
        # usando HMAC SHA1. Esta será binaria.
        signature = hmac.new(decoded_key, url_to_sign, hashlib.sha1)
        # Codificar la firma binaria usando base64 para insertarlo en la URL
        encoded_signature = base64.urlsafe_b64encode(signature.digest())
        original_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query
        full_url = original_url + '&signature=' + encoded_signature
        return full_url


def parse_json(url=''):
    """
    Decodificar la respuesta del archivo json que devuelve la API
    """
    req = urllib2.Request(url)
    opener = urllib2.build_opener()
    f = opener.open(req)
    d = simplejson.load(f)

    if not d['status'] == 'OK':
        raise Exception('Error. API Google Maps devolvió status: {}'.format(d['status']))

    addresses = d['destination_addresses']

    i = 0
    durations = [0] * len(addresses)
    for row in d['rows'][0]['elements']:
        if not row['status'] == 'OK':
            raise Exception('Error. API Google Maps devolvió status: {}'.format(row['status']))
            durations[i] = 9999
        else:
            if 'duration_in_traffic' in row:
                durations[i] = row['duration_in_traffic']['value'] / 60
            else:
                durations[i] = row['duration']['value'] / 60
        i += 1
    return [addresses, durations]


def geocode_address(address='',
                    access_type='personal',
                    config_path='config/'):
    """
    Para el cálculo de distancias entre 2 lugares, se necesita la [lat, lng] en lugar de la dirección.
    """
    # Convertir el origen y el destino en una URL
    if address == '':
        raise Exception('la dirección no puede estar en blanco.')
    elif isinstance(address, str) or isinstance(address, unicode):
        address_str = address.replace(' ', '+')
    else:
        raise Exception('la dirección debe ser una cadena.')
    # access_type is either 'personal' or 'business'
    if access_type not in ['personal', 'business']:
        raise Exception("el tipo de acceso puede ser 'personal' o de 'negocios'.")

    # Obtener la llave de la API de Google de un archivo externo tipo .config
    # Si se esta usando Google Maps para negocios (debido al tráfico necesario de consultas),
    # este archivo debe tener el siguiente formato:
    #
    # [api]
    # client_id=<your client id>
    # crypto_key=<your crypto key>
    #
    # Si se esta usando la versión personal de Google Maps, el formato debe ser:
    #
    # [api]
    # api_number=<your api number>
    #
    config = ConfigParser.SafeConfigParser()
    config.read('{}google_maps.cfg'.format(config_path))
    if access_type == 'personal':
        key = config.get('api', 'api_number')
    if access_type == 'business':
        client = config.get('api', 'client_id')

    # Convertimos la cadena en una URL, que podamos usar
    # usamos la función urlparse() en la consulta
    # Esta URL ya debe estar codificada correctamente
    prefix = 'https://maps.googleapis.com/maps/api/geocode/json'
    if access_type == 'personal':
        url = urlparse.urlparse('{0}?address={1}&key={2}'.format(prefix,
                                                                 address_str,
                                                                 key))
        full_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query
    if access_type == 'business':
        url = urlparse.urlparse('{0}?address={1}&client={2}'.format(prefix,
                                                                    address_str,
                                                                    client))
        # Obtener la private_key usada al solicitar la API
        private_key = config.get('api', 'crypto_key')
        # Requerimos juntar la URL y la consulta como parte de la cadena
        url_to_sign = url.path + "?" + url.query
        # Decodificar la private key a su forma binaria
        decoded_key = base64.urlsafe_b64decode(private_key)
        # Crear a una firma usando la llave y la URL-codificada
        # usando HMAC SHA1. Esta será binaria.
        signature = hmac.new(decoded_key, url_to_sign, hashlib.sha1)
        # Codificar la firma binaria usando base64 para insertarlo en la URL
        encoded_signature = base64.urlsafe_b64encode(signature.digest())
        original_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query
        full_url = original_url + '&signature=' + encoded_signature

    # Solicitar el geocode de la dirección
    req = urllib2.Request(full_url)
    opener = urllib2.build_opener()
    f = opener.open(req)
    d = simplejson.load(f)

    # Decoficar el json para obtener el geocode
    if not d['status'] == 'OK':
        raise Exception('Error. Google Maps API return status: {}'.format(d['status']))
    geocode = [d['results'][0]['geometry']['location']['lat'],
               d['results'][0]['geometry']['location']['lng']]
    return geocode


def select_destination(origin='',
                       angle='',
                       radius='',
                       access_type='personal',
                       config_path='config/'):
    """
    Dada una distancia y un ángulo polar, se calcula el geocode del destino en base al punto de origen.
    """
    if origin == '':
        raise Exception('el origen no puede estar en blanco.')
    if angle == '':
        raise Exception('el ángulo no puede estar en blanco.')
    if radius == '':
        raise Exception('el radio no puede estar en blanco.')

    if isinstance(origin, str):
        origin_geocode = geocode_address(origin, access_type, config_path)
    elif isinstance(origin, list) and len(origin) == 2:
        origin_geocode = origin
    else:
        raise Exception('el origen debe ser una lista de [lat, lng] o una lista de direcciones.')

    # Encontrar las localizaciones en la esfera con la distancia 'radio' junto al 'ánglulo' polar desde el origen
    # Esto utiliza el semiverseno en lugar de la distancia pitagórica simple en el espacio euclidiano.
    # debido a que las esferas son mas complejas en este tipo de cálculo que los planos.
    r = 6378.09999805  # Radio de la tierra en kilómetros
    bearing = radians(angle)  # Ángulo convertido en radianes
    lat1 = radians(origin_geocode[0])
    lng1 = radians(origin_geocode[1])
    lat2 = asin(sin(lat1) * cos(radius / r) + cos(lat1) * sin(radius / r) * cos(bearing))
    lng2 = lng1 + atan2(sin(bearing) * sin(radius / r) * cos(lat1), cos(radius / r) - sin(lat1) * sin(lat2))
    lat2 = degrees(lat2)
    lng2 = degrees(lng2)
    return [lat2, lng2]


def get_bearing(origin='',
                destination=''):
    """
    Calcular el ángulo desde el origen al destino
    """
    if origin == '':
        raise Exception('el origen no puede estar en blanco')
    if destination == '':
        raise Exception('el destino no puede estar en blanco')

    bearing = atan2(sin((destination[1] - origin[1]) * pi / 180) * cos(destination[0] * pi / 180),
                    cos(origin[0] * pi / 180) * sin(destination[0] * pi / 180) -
                    sin(origin[0] * pi / 180) * cos(destination[0] * pi / 180) * cos((destination[1] - origin[1]) * pi / 180))
    bearing = bearing * 180 / pi
    bearing = (bearing + 360) % 360
    return bearing


def sort_points(origin='',
                iso='',
                access_type='personal',
                config_path='config/'):
    """
    Poner los puntos de la isocrona en el orden correcto
    """
    if origin == '':
        raise Exception('el origen no puede estar en blanco.')
    if iso == '':
        raise Exception('iso no puede estar en blanco.')

    if isinstance(origin, str):
        origin_geocode = geocode_address(origin, access_type, config_path)
    elif isinstance(origin, list) and len(origin) == 2:
        origin_geocode = origin
    else:
        raise Exception('el origen debe ser una lista de [lat, lng] o una lista de direcciones.')

    bearings = []
    for row in iso:
        bearings.append(get_bearing(origin_geocode, row))

    points = zip(bearings, iso)
    sorted_points = sorted(points)
    sorted_iso = [point[1] for point in sorted_points]
    return sorted_iso


def get_isochrone(origin='',
                  duration='',
                  number_of_angles=12,
                  tolerance=0.1,
                  access_type='personal',
                  config_path='config/'):
    """
    Juntando las partes.
    Dado un origen y un tiempo a reprentar en la isocrona (por ejemplo 15 minutos desde el origen)
    se usa la API de matrices de distancias de Google Maps para chequear los tiempos de viaje en cada uno de los ángulos desde un origen y de esta manera obtener un
    polígonocon una cantidad de lados igual al número de ángulos. Realizar una busqueda binaria en base al radio en cada ángulo hasta que el tiempo de viaje devuelto
    sea el buscado.
    origen = lista de direcciones o [lat, lng]
    duración = minutos a representar en la isocrona
    número de ángulos = cantidad de ángulos a calcular (resolución de la isocrona)
    tolerancia = cantidad de minutos de toleracia para el cálculo de la isocrona
    tipo de acceso = de negocios 'business' o 'personal' (se requiere business según la cantidad de información a solicitar)
    config_path = ubicación del archivo en donde se encuentran las llaves de las API a solicitar
    """
    if origin == '':
        raise Exception('el origen no puede estar en blanco')
    if duration == '':
        raise Exception('la duración no puede estar en blanco')
    if not isinstance(number_of_angles, int):
        raise Exception('número de angulos debe ser un entero')

    if isinstance(origin, str):
        origin_geocode = geocode_address(origin, access_type, config_path)
    elif isinstance(origin, list) and len(origin) == 2:
        origin_geocode = origin
    else:
        raise Exception('el origen debe ser una lista de [lat, lng] o una lista de direcciones.')

    # Hacer una lista de los radios, con un elemento para cada ángulo,
    # los mismos seran actualizados de manera iterativa hasta que se encuentre la isocrona
    rad1 = [duration / 12] * number_of_angles  # radio inicial basado en una velocidad de 8 Km/h
    phi1 = [i * (360 / number_of_angles) for i in range(number_of_angles)]
    data0 = [0] * number_of_angles
    rad0 = [0] * number_of_angles
    rmin = [0] * number_of_angles
    rmax = [1.25 * duration] * number_of_angles  # radio máximo basado en una velocidad de 120 Km/h
    iso = [[0, 0]] * number_of_angles

    # Contador para evitar errores
    j = 0

    # Comenzar con la busqueda binaria
    while sum([a - b for a, b in zip(rad0, rad1)]) != 0:
        rad2 = [0] * number_of_angles
        for i in range(number_of_angles):
            iso[i] = select_destination(origin, phi1[i], rad1[i], access_type, config_path)
            time.sleep(0.1)
        url = build_url(origin, iso, access_type, config_path)
        data = parse_json(url)
        for i in range(number_of_angles):
            if (data[1][i] < (duration - tolerance)) & (data0[i] != data[0][i]):
                rad2[i] = (rmax[i] + rad1[i]) / 2
                rmin[i] = rad1[i]
            elif (data[1][i] > (duration + tolerance)) & (data0[i] != data[0][i]):
                rad2[i] = (rmin[i] + rad1[i]) / 2
                rmax[i] = rad1[i]
            else:
                rad2[i] = rad1[i]
            data0[i] = data[0][i]
        rad0 = rad1
        rad1 = rad2
        j += 1
        if j > 30:
            raise Exception("La consulta demoró demasiado tiempo.")

    for i in range(number_of_angles):
        iso[i] = geocode_address(data[0][i], access_type, config_path)
        time.sleep(0.1)

    iso = sort_points(origin, iso, access_type, config_path)
    return iso


def generate_isochrone_map(origin='',
                           duration='',
                           number_of_angles=12,
                           tolerance=0.1,
                           access_type='personal',
                           config_path='config/'):
    """
    Usar la función get_isochrone y generar un archivo .html usando su salida.
    """
    if origin == '':
        raise Exception('el origen no puede estar en blanco')
    if duration == '':
        raise Exception('el tiempo de viaje no puede estar en blanco')
    if not isinstance(number_of_angles, int):
        raise Exception('el número de angulos debe ser un entero')

    if isinstance(origin, str):
        origin_geocode = geocode_address(origin, access_type, config_path)
    elif isinstance(origin, list) and len(origin) == 2:
        origin_geocode = origin
    else:
        raise Exception('el origen debe ser una lista de [lat, lng] o una lista de direcciones.')

    iso = get_isochrone(origin, duration, number_of_angles, tolerance, access_type, config_path)

    htmltext = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no">
    <meta charset="utf-8">
    <title>Isochrone</title>
    <style>
      html, body, #map-canvas {{
        height: 100%;
        margin: 0px;
        padding: 0px
      }}
    </style>

    <script src="https://maps.googleapis.com/maps/api/js?v=3.exp&signed_in=true"></script>

    <script>
    function initialize() {{
      var mapOptions = {{
        zoom: 14,
        center: new google.maps.LatLng({0},{1}),
        mapTypeId: google.maps.MapTypeId.TERRAIN
      }};

      var map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);

      var marker = new google.maps.Marker({{
          position: new google.maps.LatLng({0},{1}),
          map: map
      }});

      var isochrone;

      var isochroneCoords = [
    """.format(origin_geocode[0], origin_geocode[1])

    for i in iso:
        htmltext += 'new google.maps.LatLng({},{}), \n'.format(i[0], i[1])

    htmltext += """
      ];

      isochrone = new google.maps.Polygon({
        paths: isochroneCoords,
        strokeColor: '#000',
        strokeOpacity: 0.5,
        strokeWeight: 1,
        fillColor: '#000',
        fillOpacity: 0.25
      });

      isochrone.setMap(map);

    }

    google.maps.event.addDomListener(window, 'load', initialize);
    </script>

    </head>
    <body>
    <div id="map-canvas"></div>
    </body>
    </html>
    """

    with open('isochrone.html', 'w') as f:
        f.write(htmltext)

    return iso

