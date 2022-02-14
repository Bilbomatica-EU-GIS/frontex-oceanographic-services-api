import json
import re
import requests

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from datetime import datetime
from datetime import timedelta
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
from pyproj import Transformer
from xml.etree import ElementTree as ETree

app = Flask(__name__, template_folder='swagger/templates')
CORS(app)

spec = APISpec(
    title='marine_data',
    version='1.0.0',
    openapi_version='3.0.2',
    plugins=[FlaskPlugin(), MarshmallowPlugin()]
)


@app.route('/marine_data/api/swagger.json')
def create_swagger_spec():
    return jsonify(spec.to_dict())


@app.route('/marine_data/docs')
@app.route('/marine_data/docs/<path:path>')
def swagger_docs(path=None):
    if not path or path == 'index.html':
        return render_template('index.html', base_url='/marine_data/docs')
    else:
        return send_from_directory('./swagger/static', path)


@app.route('/marine_data/data/<string:lon>/<string:lat>', methods=['GET'])
def data(lon, lat):
    """Get sea variables
        ---
        get:
            description: Get List of sea parameters data from an specific point
            responses:
                200:
                    description: Return a JSON with the parameters
                    content:
                        application/json:
                            schema:
    """
    response_json = {
        "Location": {
            "longitude": lon,
            "latitude": lat
        },
        "Data": []
    }
    lon_aux = lon.replace(".", "") if lon[0] != "-" else lon[1:].replace(".", "")
    lat_aux = lat.replace(".", "") if lat[0] != "-" else lat[1:].replace(".", "")

    if lon_aux.isnumeric() and lat_aux.isnumeric():
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        projected = transformer.transform(lon, lat)
        lon_proj = projected[0]
        lat_proj = projected[1]

        with open("config.json") as jsonFile:
            config = json.load(jsonFile)
            jsonFile.close()

        url_capabilities = config["ServiceURL"] + "&request=GetCapabilities&version=1.3.0&service=WMS"
        response_capabilities = requests.get(url_capabilities)

        if 'xml' in response_capabilities.headers['Content-Type']:
            tree = ETree.fromstring(response_capabilities.content)
            m = re.match('\{.*\}', tree.tag)
            namespace = m.group(0) if m else ''

            for layer in tree.findall(namespace + 'Capability//' + namespace + 'Layer'):
                name = layer.find(namespace + 'Name').text
                parameter = get_parameter(config["Parameters"], name)

                if parameter is not None:
                    time_dimension = layer.find(namespace + 'Dimension').text
                    time_from = datetime.strptime(time_dimension.split("/")[0], "%Y-%m-%dT%H:%M:%SZ")
                    time_to = datetime.strptime(time_dimension.split("/")[1], "%Y-%m-%dT%H:%M:%SZ")
                    if time_from < datetime.now():
                        time_from = datetime.now()
                    if time_to >= datetime.now() + timedelta(days=7):
                        time_to = datetime.now() + timedelta(days=7)
                    temporal_extent = time_from.strftime("%Y-%m-%dT%H:00:00Z") + "/" + time_to.strftime("%Y-%m-%dT%H:00:00Z")

                    data_info = get_data(config["ServiceURL"], parameter["ParameterName"], parameter["Units"],
                                         parameter["ParameterId"], lat_proj, lon_proj, temporal_extent)

                    if data_info is not None:
                        response_json["Data"].append(data_info)

    return response_json


with app.test_request_context():
    spec.path(view=data)


def get_parameter(parameters, parameter_name):
    response_parameter = None
    for parameter in parameters:
        if parameter["ParameterId"] == parameter_name:
            response_parameter = parameter
            break

    return response_parameter


def get_data(service_url, parameter, units, parameter_id, lat, lon, temporal_extent):
    try:
        info_data = {
            "Variable": parameter,
            "VariableId": parameter_id,
            "Units": units,
            "Data": []
        }

        url_info = service_url
        url_info += r'&service=WMS&request=GetFeatureInfo&version=1.3.0'
        url_info += r'&QUERY_LAYERS=' + parameter_id + '&layers=' + parameter_id
        url_info += r'&crs=EPSG:3857'
        url_info += r'&bbox=' + (str(float(lon) - 0.0001)) + ',' + (str(float(lat) - 0.0001)) + ',' + \
                    (str(float(lon) + 0.0001)) + ',' + (str(float(lat) + 0.0001))
        url_info += r'&height=101&width=101&i=50&j=50'
        url_info += r'&time=' + temporal_extent
        url_info += r'&INFO_FORMAT=application/json'

        response_info = requests.get(url_info)
        json_info = json.loads((str(response_info.content)[str(response_info.content).index("{"):])[:-1])

        for feature_info in json_info["features"]:
            feature = {"DateTime": feature_info["properties"]["time"], "Value": feature_info["properties"]["value"]}
            info_data["Data"].append(feature)

        return info_data

    except:
        return None


if __name__ == '__main__':
    app.run(debug=True)
