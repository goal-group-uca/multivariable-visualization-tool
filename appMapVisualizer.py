import csv

from kivymd.app import MDApp
from kivymd.uix.boxlayout import BoxLayout
from kivymd.uix.textfield import MDTextFieldRect
from kivymd.uix.button import MDRectangleFlatIconButton
from kivymd.uix.screen import MDScreen
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.factory import Factory

from getSolutionDetails import main_get_solution_details
from MapVisualizerSimple import main_map_visualizer

import webbrowser

from os.path import realpath
from os import listdir

from kivy.lang.builder import Builder
Builder.load_file('xBusRouteVisualizer.kv')



class BusRouteVisualizer(BoxLayout):
    def __init__(self, **var_args):
        super(BusRouteVisualizer, self).__init__(**var_args)
        self.orientation = 'vertical'

        self.bus_routes = {}
        self.bus_routes_solutions = {}

        self.bus_routes_to_plot = {}
        self.switcher = {'One-way': 0,  'Back-way': 1, 'Round-trip': 2}

        dir_ = 'bus_routes/'
        dir_solutions = 'solutions/'
        routes = listdir(dir_)
        routes.sort()
        for route in routes:
            key = "Bus Route " + route.replace('processed_bus_route_', '').replace('_random_', ' ').replace('.csv', '').replace('.0%','%')
            values = []
            with open(f"{dir_solutions}Hybrid_Bus{key.split(' ')[3].replace('ze', '')}_individuals{key.split(' ')[2]}.pf", 'r') as csvfile:
                csv_reader = csv.reader(csvfile, delimiter = ' ', doublequote = False)
                line_count = 0
                for row in csv_reader:
                    if line_count != 0:
                        values.append([float(row[0]), float(row[1]), [int(x) for x in row[2].replace('[','').replace(']','').split(',')]])
                    line_count += 1
            self.bus_routes_solutions[key] = values
            self.bus_routes[key] = route

        self.counter=1
    
    def load_bus_routes(self):
        return self.bus_routes.keys()
    
    def show_solutions(self, selected_route):
        self.solutions = []
        for index, val in enumerate(self.bus_routes_solutions[selected_route]):
            self.solutions.append(f"{index}. Green kms: {(val[1] * -1):.3} | CO2 kgs: {val[0]:.3}")
        
        return self.solutions
    
    def add_bus_route(self, bus_route, solution, bus_direction, recharge, dashed, list_bus_routes):
        index = solution.split('.')[0]
        if bus_route not in list_bus_routes:
            list_bus_routes.append(f'{bus_route} - {index}')
        self.bus_routes_to_plot[f'{bus_route} - {index}'] = [self.bus_routes_solutions[bus_route][int(index)][2], self.switcher[bus_direction], recharge, self.bus_routes[bus_route], dashed]
    
    def delete_bus_route(self, bus_route, list_bus_routes):
        if bus_route != "":
            list_bus_routes.pop(list_bus_routes.index(bus_route))

            del self.bus_routes_to_plot[bus_route]

    
    def create_maps(self, CSV_filename, loading_screen):
        for key in self.bus_routes_to_plot.keys():
            solution, bus_direction, recharge_bool, input_filename, dashed = self.bus_routes_to_plot[key]
            main_get_solution_details(f"bus_routes/{input_filename}", solution, f"{key}_{CSV_filename}", recharge_bool)
        main_map_visualizer(self.bus_routes_to_plot, CSV_filename, bus_direction)
        loading_screen.dismiss()
    
    def increase(self):
        self.counter += 1
        self.ids['counter_text'].text = str(self.counter)

    def decrease(self):
        if self.counter <= 1:
            pass
        else:
            self.counter -= 1
            self.ids['counter_text'].text = str(self.counter)

    def add_HTML_text(self, text):
        self.mdtextfield.text = text
    
    def checkbox_true(self, variable_layout):
        self.label1 = Label(size_hint=(0.1, 1))
        self.mdtextfield = MDTextFieldRect(hint_text='Path to input HTML file...',
                                           size_hint=(1, 1),
                                           pos_hint={'center_x':0.5, 'center_y':0.5})
        self.label2 = Label(size_hint=(0.1, 1))
        self.mdrectbutton = MDRectangleFlatIconButton(icon='file',
                                                      size_hint=(0.6,1),
                                                      pos_hint={'center_x':0.5, 'center_y':0.5},
                                                      text='Choose HTML file...',
                                                      on_release=Factory.SelectHTML().open)

        variable_layout.add_widget(self.label1)
        variable_layout.add_widget(self.mdtextfield)
        variable_layout.add_widget(self.label2)
        variable_layout.add_widget(self.mdrectbutton)

    
    def checkbox_false(self, variable_layout):
        variable_layout.remove_widget(self.label1)
        variable_layout.remove_widget(self.mdtextfield)
        variable_layout.remove_widget(self.label2)
        variable_layout.remove_widget(self.mdrectbutton)
        
    def open_maps(self, CSV_filename):
        emission_path = realpath(f'maps/emission_map_{CSV_filename}.html')
        energy_path = realpath(f'maps/energy_map_{CSV_filename}.html')
        slope_path = realpath(f'maps/slope_map_{CSV_filename}.html')

        webbrowser.open(f'file://{emission_path}')
        print(emission_path)
        webbrowser.open(f'file://{energy_path}')
        print(energy_path)
        webbrowser.open(f'file://{slope_path}')
        print(slope_path)


class BusRouteVisualizerApp(MDApp):
    def build(self):
        self.theme_cls.theme_style="Dark"
        return BusRouteVisualizer()
    


if __name__ == '__main__':
    BusRouteVisualizerApp().run()