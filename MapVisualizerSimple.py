import branca
import matplotlib.pyplot as plt
import matplotlib
import contextily as cx
import geopandas as gpd
from scipy import stats
import pandas as pd
import numpy as np
import seaborn as sns
import folium
import math
import requests
import json
import copy

from shapely.geometry import Point, LineString
from ReadRoute import read_route
from Bus import Bus

pd.options.mode.chained_assignment = None

config_input_path = "output/processed_bus_route_M6_random_0_bestSolNoRecharge_BusM6.csv"

def create_new_dataset(data, mode = 2):
    new_data = []
    get_data = False if mode == 1 else True
    for i, row in data.iterrows():
        if row['Final Stop'] == 1:
            x = float(row["To"].replace("(", "").replace(")", "").split(",")[0])
            y = float(row["To"].replace("(", "").replace(")", "").split(",")[1])
            altitude = float(row["Altitude To"])
            time = float(row["Time"])
            soc = float(row["Remaining charge %"])
            distance = float(row["Distance"])
            energy = float(row["Energy consumed"])
            emissions = float(row["CO2 emissions"])
            bus_stop = 1
            new_data.append(pd.Series([x, y, altitude, distance, time, soc, energy, emissions, bus_stop]))
            if mode == 0:
                break
            elif mode == 1:
                get_data = True
        if i == 0 and get_data:
            x = float(row["From"].replace("(", "").replace(")", "").split(",")[0])
            y = float(row["From"].replace("(", "").replace(")", "").split(",")[1])
            altitude = float(row["Altitude From"])
            time = 0
            distance = 0
            soc = 100
            energy = 0
            emissions = 0
            bus_stop = 1
            new_data.append(pd.Series([x, y, altitude, distance, time, soc, energy, emissions, bus_stop]))

            x = float(row["To"].replace("(", "").replace(")", "").split(",")[0])
            y = float(row["To"].replace("(", "").replace(")", "").split(",")[1])
            altitude = float(row["Altitude To"])
            time = float(row["Time"])
            soc = float(row["Remaining charge %"])
            distance = float(row["Distance"])
            energy = float(row["Energy consumed"])
            emissions = float(row["CO2 emissions"])
            bus_stop = data.iloc[i + 1, :]['Bus Stop']
            new_data.append(pd.Series([x, y, altitude, distance, time, soc, energy, emissions, bus_stop]))
        elif i == (len(data) - 1) and get_data:
            x = float(row["To"].replace("(", "").replace(")", "").split(",")[0])
            y = float(row["To"].replace("(", "").replace(")", "").split(",")[1])
            altitude = float(row["Altitude To"])
            time = float(row["Time"])
            soc = float(row["Remaining charge %"])
            distance = float(row["Distance"])
            energy = float(row["Energy consumed"])
            emissions = float(row["CO2 emissions"])
            bus_stop = 1
            new_data.append(pd.Series([x, y, altitude, distance, time, soc, energy, emissions, bus_stop]))
        elif get_data:
            x = float(row["To"].replace("(", "").replace(")", "").split(",")[0])
            y = float(row["To"].replace("(", "").replace(")", "").split(",")[1])
            altitude = float(row["Altitude To"])
            time = float(row["Time"])
            soc = float(row["Remaining charge %"])
            distance = float(row["Distance"])
            energy = float(row["Energy consumed"])
            emissions = float(row["CO2 emissions"])
            bus_stop = data.iloc[i + 1, :]['Bus Stop']
            new_data.append(pd.Series([x, y, altitude, distance, time, soc, energy, emissions, bus_stop]))
        
    new_data = pd.DataFrame(new_data)
    new_data.columns = ["Y", "X", "Altitude", "distance", "Time", "SoC", "energy", "emissions", 'Bus Stop']

    return new_data

class MapVisualization:
    def __init__(self, bus_routes_to_plot, CSV_filename, mode=2):
        self.data = []
        self.dashed = []
        self.bus_routes_to_plot = [] 
        for key in bus_routes_to_plot.keys():
            dataset = pd.read_csv(f"output/{key}_{CSV_filename}.csv", sep=',', index_col="Unnamed: 0.1")
            dataset = create_new_dataset(dataset, mode)
            self.bus_routes_to_plot.append(key)
            self.data.append(dataset)
            self.dashed.append(bus_routes_to_plot[key][-1])
        self.colors = {}

    def setGeometry(self):
        self.gdf = []
        for dataset in self.data:
            gdf = gpd.GeoDataFrame(dataset, geometry=gpd.points_from_xy(
            dataset["X"], dataset["Y"]), crs=4326)
            self.gdf.append(gdf)

    def getLines(self, pairs=None):
        self.lines_to_plot = []
        self.all_consumo = []
        self.all_desnivel = []
        self.all_emisiones = []

        for index2,pair in enumerate(pairs):
            lines = []
            values = []

            for i in pair:
                consumo = float(self.gdf[index2].loc[i[1]]['energy'])
                dist = self.gdf[index2].at[i[1], 'distance']
                time = self.gdf[index2].at[i[1], 'Time']
                deltaH = self.gdf[index2].at[i[1], 'Altitude'] - self.gdf[index2].at[i[0], 'Altitude']
                desnivel = (deltaH * 100)/(dist)
                emisiones = float(self.gdf[index2].loc[i[1]]['emissions'])
                aux = []
                
                # Call the OSMR API
                _from = [self.data[index2]["X"][i[0]], self.data[index2]["Y"][i[0]]]
                _to = [self.data[index2]["X"][i[1]], self.data[index2]["Y"][i[1]]]

                r = requests.get(f"http://router.project-osrm.org/route/v1/car/{_from[0]},{ _from[1]};{_to[0]},{_to[1]}?geometries=geojson""")


                routes = json.loads(r.content)
                route_1 = routes.get("routes")[0]
                coordinates = copy.deepcopy(route_1["geometry"]["coordinates"])

                points = []
    
                for index, coord in enumerate(coordinates):
                    point = Point(coord[0], coord[1])
                    points.append(point)
                
                aux = []
                for index in range(len(points)-1):
                    aux.append([points[index], points[index+1]])
                
                for l in aux:
                    lines.append(LineString(l))
                    values.append([consumo, desnivel, time, emisiones])
                
                self.all_consumo.append(consumo)
                self.all_desnivel.append(desnivel)
                self.all_emisiones.append(emisiones)

            gdf_lines2 = gpd.GeoDataFrame(values, crs=4326, geometry=lines)
            gdf_lines2.columns = ['consumo', 'desnivel', 'tiempo', 'emisiones', 'geometry']
            gdf_lines2.reset_index(inplace=True, drop=True)
            self.lines_to_plot.append(gdf_lines2)

    def pairsByDistance(self):
        pairs = []
        
        for gdf in self.gdf:
            pairs.append([])
            for i, _ in gdf.iterrows():
                if i != 0:
                    pairs[-1].append((i - 1, i))
        return pairs

    def plotMapaConsumo(self, filename = ''):
        m = folium.Map(max_bounds=True, tiles='CartoDB Positron')
        folium.TileLayer('openstreetmap').add_to(m)
        folium.TileLayer('Stamen Terrain').add_to(m)

        self.colors = {}
        map_colors = {}

        for index, gdf_lines2 in enumerate(self.lines_to_plot):

            for _, row in gdf_lines2.iterrows():
                feature = row['consumo']
                norm = matplotlib.colors.Normalize(
                    vmin=np.array(self.all_consumo).min(), vmax=np.array(self.all_consumo).max())
                cmap = matplotlib.colormaps['RdYlGn_r']
                rgba = cmap(norm(feature))
                self.colors[rgba] = feature
                map_colors[feature] = matplotlib.colors.rgb2hex(rgba)
        
        self.colors = {k: v for k, v in sorted(self.colors.items(), key=lambda item: item[1])}
        if len(self.colors.keys()) > 1:
            colormap = branca.colormap.LinearColormap(
                colors=self.colors.keys(), vmin=np.array(self.all_consumo).min(), vmax=np.array(self.all_consumo).max(),
                tick_labels= [np.array(self.all_consumo).min(),
                            ((np.array(self.all_consumo).max() + np.array(self.all_consumo).min()) / 2 + np.array(self.all_consumo).min()) / 2,
                            (np.array(self.all_consumo).max() + np.array(self.all_consumo).min()) / 2,
                            ((np.array(self.all_consumo).max() + np.array(self.all_consumo).min()) / 2 + np.array(self.all_consumo).max()) / 2,
                                np.array(self.all_consumo).max()])
            colormap.caption = 'Energy Consumption (kWh)'
            colormap.add_to(m)
        else:
            colormap = branca.colormap.LinearColormap(colors=[list(self.colors.keys())[0], 'red'],
                                                        vmin=np.array(self.all_consumo).min(), vmax=1)
            colormap.caption = 'Energy Consumption (kWh)'
            colormap.add_to(m)

        for index, gdf_lines2 in enumerate(self.lines_to_plot):
            if self.dashed[index]:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['consumo']],
                                'fillOpacity': 1,
                                'weight': 4,
                                'dashArray': '5, 10'

                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            else:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['consumo']],
                                'fillOpacity': 1,
                                'weight': 4

                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            sw = self.gdf[index][['Y', 'X']].min().values.tolist()
            ne = self.gdf[index][['Y', 'X']].max().values.tolist()

            m.fit_bounds([sw, ne])
            
            bus_stops = folium.FeatureGroup(name=f"Bus Stops {self.bus_routes_to_plot[index]}").add_to(m)
            for index, row in self.data[index].iterrows():
                if row['Bus Stop'] == 1:
                    marker = folium.Marker(
                        location=[row['Y'], row['X']],
                        icon=folium.Icon(icon='bus', prefix='fa')
                        )
                    bus_stops.add_child(marker)
                    
        folium.LayerControl().add_to(m)           
        m.save(f'maps/energy_map_{filename}.html')



    def plotMapaEmisiones(self, filename = '', map = "", bus_stop_icons = True):
        m = folium.Map(max_bounds=True, tiles='CartoDB Positron')
        folium.TileLayer('openstreetmap').add_to(m)
        folium.TileLayer('Stamen Terrain').add_to(m)

        self.colors = {}
        map_colors = {}

        for index, gdf_lines2 in enumerate(self.lines_to_plot):
            for _, row in gdf_lines2.iterrows():
                feature = row['emisiones']
                norm = matplotlib.colors.Normalize(
                    vmin=np.array(self.all_emisiones).min(), vmax=np.array(self.all_emisiones).max())
                cmap = matplotlib.colormaps['RdYlGn_r']
                rgba = cmap(norm(feature))
                self.colors[rgba] = feature
                map_colors[feature] = matplotlib.colors.rgb2hex(rgba)
        
        self.colors = {k: v for k, v in sorted(self.colors.items(), key=lambda item: item[1])}
        if len(self.colors.keys()) > 1:
            colormap = branca.colormap.LinearColormap(
                colors=self.colors.keys(), vmin=np.array(self.all_emisiones).min(), vmax=np.array(self.all_emisiones).max(),
                tick_labels= [np.array(self.all_emisiones).min(),
                            ((np.array(self.all_emisiones).max() + np.array(self.all_emisiones).min()) / 2 + np.array(self.all_emisiones).min()) / 2,
                            (np.array(self.all_emisiones).max() + np.array(self.all_emisiones).min()) / 2,
                            ((np.array(self.all_emisiones).max() + np.array(self.all_emisiones).min()) / 2 + np.array(self.all_emisiones).max()) / 2,
                                np.array(self.all_emisiones).max()])
            colormap.caption = 'CO2 Emissions (Kg)'
            colormap.add_to(m)
        else:
            colormap = branca.colormap.LinearColormap(colors=[list(self.colors.keys())[0], 'red'],
                                                        vmin=np.array(self.all_emisiones).min(), vmax=1)
            colormap.caption = 'CO2 Emissions (Kg)'
            colormap.add_to(m)

        for index, gdf_lines2 in enumerate(self.lines_to_plot):
            if self.dashed[index]:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['emisiones']],
                                'fillOpacity': 1,
                                'weight': 4,
                                'dashArray': '5, 10'

                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            else:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['emisiones']],
                                'fillOpacity': 1,
                                'weight': 4
                                
                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            sw = self.gdf[index][['Y', 'X']].min().values.tolist()
            ne = self.gdf[index][['Y', 'X']].max().values.tolist()

            m.fit_bounds([sw, ne])
            
            bus_stops = folium.FeatureGroup(name=f"Bus Stops {self.bus_routes_to_plot[index]}").add_to(m)
            for index, row in self.data[index].iterrows():
                if row['Bus Stop'] == 1:
                    marker = folium.Marker(
                        location=[row['Y'], row['X']],
                        icon=folium.Icon(icon='bus', prefix='fa')
                        )
                    bus_stops.add_child(marker)
        folium.LayerControl().add_to(m) 
        m.save(f'maps/emission_map_{filename}.html')

    def plotMapaDesnivel(self, filename = '', map = "", bus_stop_icons = True):
        m = folium.Map(max_bounds=True, tiles='CartoDB Positron')
        folium.TileLayer('openstreetmap').add_to(m)
        folium.TileLayer('Stamen Terrain').add_to(m)

        self.colors = {}
        map_colors = {}

        for index, gdf_lines2 in enumerate(self.lines_to_plot):
            for _, row in gdf_lines2.iterrows():
                feature = row['desnivel']
                norm = matplotlib.colors.Normalize(
                    vmin=np.array(self.all_desnivel).min(), vmax=np.array(self.all_desnivel).max())
                cmap = matplotlib.colormaps['RdYlGn_r']
                rgba = cmap(norm(feature))
                self.colors[rgba] = feature
                map_colors[feature] = matplotlib.colors.rgb2hex(rgba)
        
        self.colors = {k: v for k, v in sorted(self.colors.items(), key=lambda item: item[1])}
        if len(self.colors.keys()) > 1:
            colormap = branca.colormap.LinearColormap(
                colors=self.colors.keys(), vmin=np.array(self.all_desnivel).min(), vmax=np.array(self.all_desnivel).max(),
                tick_labels= [np.array(self.all_desnivel).min(),
                            ((np.array(self.all_desnivel).max() + np.array(self.all_desnivel).min()) / 2 + np.array(self.all_desnivel).min()) / 2,
                            (np.array(self.all_desnivel).max() + np.array(self.all_desnivel).min()) / 2,
                            ((np.array(self.all_desnivel).max() + np.array(self.all_desnivel).min()) / 2 + np.array(self.all_desnivel).max()) / 2,
                                np.array(self.all_desnivel).max()])
            colormap.caption = 'Slope (%)'
            colormap.add_to(m)
        else:
            colormap = branca.colormap.LinearColormap(colors=[list(self.colors.keys())[0], 'red'],
                                                        vmin=np.array(self.all_desnivel).min(), vmax=1)
            colormap.caption = 'Slope (%)'
            colormap.add_to(m)

        for index, gdf_lines2 in enumerate(self.lines_to_plot):
            if self.dashed[index]:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['desnivel']],
                                'fillOpacity': 1,
                                'weight': 4,
                                'dashArray': '5, 10'

                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            else:
                folium.GeoJson(gdf_lines2,
                            style_function=lambda feature: {
                                'color': map_colors[feature['properties']['desnivel']],
                                'fillOpacity': 1,
                                'weight': 4
                                
                            }, name=self.bus_routes_to_plot[index]).add_to(m)
            sw = self.gdf[index][['Y', 'X']].min().values.tolist()
            ne = self.gdf[index][['Y', 'X']].max().values.tolist()

            m.fit_bounds([sw, ne])

            bus_stops = folium.FeatureGroup(name=f"Bus Stops {self.bus_routes_to_plot[index]}").add_to(m)
            for index, row in self.data[index].iterrows():
                if row['Bus Stop'] == 1:
                    marker = folium.Marker(
                        location=[row['Y'], row['X']],
                        icon=folium.Icon(icon='bus', prefix='fa')
                        )
                    bus_stops.add_child(marker)
        folium.LayerControl().add_to(m)           
        m.save(f'maps/slope_map_{filename}.html')

def main_map_visualizer(bus_routes_to_plot, filename, bus_direction):
    mapa = MapVisualization(bus_routes_to_plot, filename, bus_direction)
    mapa.setGeometry()
    pairs = mapa.pairsByDistance()
    mapa.getLines(pairs=pairs)
    mapa.plotMapaDesnivel(filename)
    mapa.plotMapaConsumo(filename)
    mapa.plotMapaEmisiones(filename)


if __name__ == '__main__':
    mapa = MapVisualization(config_input_path)
    mapa.setGeometry()
    pairs = mapa.pairsByDistance()
    mapa.getLines(pairs=pairs)
    mapa.plotMapaDesnivel()
    mapa.plotMapaConsumo()
    mapa.plotMapaEmisiones()

