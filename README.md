# Frontex-oceanographic-services-api
This Flask API provides the data of a given WMS service for a given latitude and longitude provided in EPSG:4326.

## Configuration
In the file config.json the WMS can be configured changing the endpoint in the property 'ServiceURL' and the layers that are going to be requested in each 'ParameterId' property.

## Requirements
The requirements can be installed using the pip command 'pip install -r requirements.txt'
