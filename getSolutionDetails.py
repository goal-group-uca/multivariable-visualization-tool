from matplotlib.artist import kwdoc
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import math
from ReadRoute import read_route
from Bus import Bus

config_input_solution = [100, 100, 100, 0, 100, 100, 100, 0, 100, 0, 0, 100, 0, 0, 0, 100, 0, 100, 100, 100, 100, 0, 0, 100, 0, 100, 100, 100, 100, 100, 0, 100, 100, 100, 100, 100, 0, 100, 0, 100, 100, 100, 0, 100, 0, 100, 100, 0, 100, 100, 0, 100, 100, 100, 0, 0, 100, 100, 0, 0, 100, 100, 100, 0, 0, 100]
config_input_path = "output/processed_bus_route_18_random_0.0%ze.csv"
config_input_surname = "pruebasolucion_Bus18"
config_recharge = False


def vehicle_specific_power(v: float, slope: float, acc: float, m: float = 1950, A: float = 7):
    g = 9.80665 # Gravity
    Cr=0.013 # Rolling resistance coefficient
    Cd=0.7 # Drag coefficient
    ro_air=1.225 # Air density
    alpha = math.atan(slope) #Elevation angle in radians
    aux_energy = 2 #Auxiliar energy consumption in kW - 3kW with AC off or 12kW with AC on

    #Vehicle efficiencies
    n_dc = 0.90
    n_m = 0.95
    n_t = 0.96
    n_b = 0.97
    n_g = 0.90

    Frff = g * Cr * m * math.cos(alpha) # Rolling friction force
    Fadf = ro_air * A * Cd * math.pow(v, 2) / 2 # Aerodynamic drag force
    Fhcf = g * m * math.sin(alpha) # Hill climbing force
    Farf = m * acc # Acceleration resistance force
    Fttf = Frff + Fadf + Fhcf + Farf # Total force in Newtons

    power = (Fttf * v) / 1000 # Total energy in kW

    #Drivetrain model (efficiency)
    rbf = 1-math.exp(-v*0.36) #Regenerative braking factor
    if power<0:
        total_n = n_dc*n_g*n_t*n_b #Total drivetrain efficiency
        total_power = aux_energy/n_b + rbf*power*total_n
    else:
        total_n = n_dc*n_m*n_t*n_b; #Total drivetrain efficiency
        total_power = aux_energy/n_b + power/total_n


    #print("Frff: {}, Fadf: {}, Fhcf: {}".format(Frff, Fadf, Fhcf))
    return  total_power

def decrease_battery_charge(remaining_charge, section_charge, bus_charge):
    if (remaining_charge - section_charge) > bus_charge:
        return bus_charge
    else:
        return remaining_charge - section_charge

def acceleration_section_power(vo: float, vf: float, acc: float, slope: float, section_distance: float, 
                                section_duration: float, green_percent: float, m: float = 19500, A: float = 7):
    acc_distance = (math.pow(vf, 2) - math.pow(vo, 2)) / (2 * acc)
    acc_duration = round((vf - vo) / acc)

    acc_green_energies = 0
    acc_fuel_energies = 0
    instant_speed = 0
    driven_distance = 0

    section_distance *= 1000
    green_distance = green_percent * section_distance

    if green_distance == section_distance:
        for _ in range(0, acc_duration):
            acc_green_energies += vehicle_specific_power(instant_speed, slope, acc, m, A) / 3600
            instant_speed += acc
        remaining_seconds = section_duration - acc_duration
        return acc_green_energies + vehicle_specific_power(vf, slope, 0, m, A) * remaining_seconds / 3600, [0], acc_green_energies
    elif green_distance > acc_distance:
        for _ in range(0, acc_duration):
            acc_green_energies += vehicle_specific_power(instant_speed, slope, acc, m, A) / 3600
            instant_speed += acc
        remaining_seconds = section_duration - acc_duration
        remaining_distance = section_distance - acc_distance

        remaining_green_percent = (green_distance - acc_distance)/ remaining_distance

        return acc_green_energies + vehicle_specific_power(vf, slope, acc, m, A) * remaining_seconds / 3600 * remaining_green_percent,\
            [vehicle_specific_power(vf, slope, acc, m, A) * remaining_seconds / 3600 * (1 - remaining_green_percent)],\
            acc_green_energies
    else:
        for _ in range(0, acc_duration):
            if green_distance > driven_distance:
                acc_green_energies += vehicle_specific_power(instant_speed, slope, acc, m, A) / 3600
                driven_distance = (math.pow(instant_speed, 2) - math.pow(0, 2)) / (2 * acc)
                instant_speed += acc
            else:
                acc_fuel_energies += vehicle_specific_power(instant_speed, slope, acc, m, A) / 3600
                instant_speed += acc
        remaining_seconds = section_duration - acc_duration
        return acc_green_energies, [acc_fuel_energies, vehicle_specific_power(vf, slope, 0, m, A) * remaining_seconds / 3600], acc_green_energies + acc_fuel_energies       


def get_solution_details(data, config_input_solution, path, surname, ga_recharge):
    evaluation_array = []
    route = read_route(path)
    bus = Bus(1, route)
    count = 0
    for section in route.sections:
        if section.section_type == 1:
            evaluation_array.append(1.0)
        else:
            # Si tiene una inclinación menor a -2% se hace siempre en eléctrico
            if section.slope > -0.02:
                evaluation_array.append(config_input_solution[count]/100.0)
                count += 1
            else:
                evaluation_array.append(1)
            

    """ VSP Model application in order to obtain the objectives"""
    soc_values = []
    charge_per_zone = []
    green_kms_per_zone = []
    emissions_per_zone = []
    remaining_charges = []

    first_direction_kms = 0

    total_emissions = 0
    green_kms = 0
    remaining_charge = bus.charge
    recharge = 0
    invalid = False
    for index,section in enumerate(evaluation_array):
        kW_h = 0
        fuel_kW_h = 0
        battery_kW_h = 0
        section_battery = 0
        section_emissions = 0
        section_green_kms = 0
        if section == 0:
            """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section (kWh)
            """
            if route.sections[index].bus_stop == 1:
                _, kW_h, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)
            else:

                kW_h = [vehicle_specific_power(route.sections[index].speed , route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * route.sections[index].seconds/3600]
            for kwh in kW_h:
                if kwh < 0:
                    gasoline_gallon_equivalent = 0
                    remaining_charge = decrease_battery_charge(remaining_charge, kwh / bus.electric_engine_efficiency, bus.charge)
                else:
                    gasoline_gallon_equivalent = kwh / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
            
                section_emissions += gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

            total_emissions += section_emissions

        elif section < 1:
            if route.sections[index].bus_stop == 0:
                if section < 0.50:
                    """
                        (VSP (kW) * Section Time (h) -> Energy Required to travel the section part with fuel (kWh)
                    """
                    fuel_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                    0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                    if fuel_kW_h < 0:
                        gasoline_gallon_equivalent = 0
                        remaining_charge = decrease_battery_charge(remaining_charge, fuel_kW_h / bus.electric_engine_efficiency, bus.charge)

                    else:
                        gasoline_gallon_equivalent = fuel_kW_h / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
                    
                    section_emissions = gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

                    total_emissions += section_emissions
                else:
                    """
                    (VSP (kW) * Section Time (h) -> Energy Required to travel the section part with battery (kWh)
                    """
                    battery_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                    0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                    section_battery = battery_kW_h / bus.electric_engine_efficiency
                    section_green_kms = route.sections[index].distance

                    remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
                    green_kms += section_green_kms
            else:
                """
                    (VSP (kW) * Section Time (h) -> Energy Required to travel the section(kWh)
                """

                battery_kW_h, fuel_kW_h, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)

                section_battery = battery_kW_h / bus.electric_engine_efficiency
                section_green_kms = route.sections[index].distance * section

                for kwh in fuel_kW_h:
                    if kwh < 0:
                        gasoline_gallon_equivalent = 0
                        remaining_charge = decrease_battery_charge(remaining_charge, kwh / bus.electric_engine_efficiency, bus.charge)
                    else:
                        gasoline_gallon_equivalent = kwh / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
                    
                    section_emissions += gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

                total_emissions += section_emissions
                remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
                green_kms += section_green_kms

        else:
            """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section (kWh)
            """
            if route.sections[index].bus_stop == 1:
                kW_h, _, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)
            else:

                kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * route.sections[index].seconds/3600


            section_battery = kW_h / bus.electric_engine_efficiency
            section_green_kms = route.sections[index].distance

            remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
            green_kms += section_green_kms

        #print("{} : {} ".format(route.sections[index].bus_stop, section))
        #print("{} , {} , {}".format(kW_h, battery_kW_h, fuel_kW_h))
        #input('')

        if (index + 1) >= len(route.sections) or route.sections[index + 1].bus_stop == 1:
            recharge = recharge / bus.electric_engine_efficiency * 0.5
            if remaining_charge + recharge > bus.charge:
                remaining_charge = bus.charge
            else:
                remaining_charge += recharge
            recharge = 0
        if  ga_recharge and route.sections[index].final_stop == 1:
            remaining_charge = bus.charge
            #final_stop = index
        if route.sections[index].final_stop == 1:
            first_direction_kms = green_kms
        if remaining_charge < 0:
            invalid = True
            
        soc_values.append(remaining_charge/bus.charge * 100)
        remaining_charges.append(remaining_charge)
        charge_per_zone.append(section_battery)
        emissions_per_zone.append(section_emissions)
        green_kms_per_zone.append(section_green_kms)


        '''print("Section: {}".format(section))
        print("Energia bateria: {}".format(battery_kW_h))
        print("Energia fuel: {}".format(fuel_kW_h))
        print("Energia: {}".format(kW_h))
        print()
        print("Emisiones: {}".format(section_emissions))
        print("Kms verdes: {}".format(section_green_kms))

        input(str(index))'''

    # Penalizing invalid solutions
    #print(green_kms)

    if invalid:
        solution, green_kms, total_emissions, _ = new_repair_solution(config_input_solution, remaining_charges, green_kms, total_emissions, route, bus)
        config_input_solution = []
        for i, section in enumerate(route.sections):
            if section.slope > -0.02 and section.section_type == 0:
                config_input_solution.append(solution[i])
        get_solution_details(data, config_input_solution, path, surname, ga_recharge)
        return
    
    data['Solution'] = evaluation_array
    data['Solution'] *= 100
    data['Energy consumed'] = charge_per_zone
    data['Remaining charge %'] = soc_values
    data['Green kms'] = green_kms_per_zone
    data['CO2 emissions'] = emissions_per_zone

    data.to_csv("output/{}.csv".format(surname))

    #print("Kms Verdes en Ida {}".format(first_direction_kms))
    
    #print("Kms Verdes en Vuelta {}".format(green_kms - first_direction_kms))

    return data

def new_repair_solution(solution, remaining_charges, green_kms, total_emissions, route, bus):
    full_solution = []
    count = 0
    for section in route.sections:
        if section.section_type == 1:
            full_solution.append(100)
        else:
            # Si tiene una inclinación menor a -2% se hace siempre en eléctrico
            if section.slope > -0.02:
                full_solution.append(solution[count])
                count += 1
            else:
                full_solution.append(100)
    
    for i, _ in enumerate(route.sections):
        if route.sections[i].slope > -0.02 and route.sections[i].section_type == 0:
            if remaining_charges[i] < 0:
                remaining_charges = section_evaluation_sub(remaining_charges, i, full_solution[i] / 100, route, bus)
                full_solution[i] = 0
    total_emissions, green_kms, remaining_charges, _ = simple_evaluate(full_solution, route, bus)

    return full_solution, -1 * green_kms, total_emissions, remaining_charges

def section_evaluation_sub(remaining_charges, index, section, route, bus):
    kW_h = 0
    section_battery = 0
    
    if section < 1:
        if route.sections[index].bus_stop == 0:
            if section > 0.50:
                """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section part with battery (kWh)
                """
                battery_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                section_battery = battery_kW_h / bus.electric_engine_efficiency

                fuel_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                for kwh in [fuel_kW_h]:
                    if kwh < 0:
                        section_battery = decrease_battery_charge(section_battery, kwh / bus.electric_engine_efficiency, bus.charge)

        else:
            """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section(kWh)
            """
            battery_kW_h, fuel_kW_h, _ = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
            route.sections[index].distance, route.sections[index].seconds, section)

            section_battery = battery_kW_h / bus.electric_engine_efficiency

            
            for kwh in fuel_kW_h:
                if kwh < 0:
                    section_battery = decrease_battery_charge(section_battery, kwh / bus.electric_engine_efficiency, bus.charge)
            
            _, fuel_kW_h, _ = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
            route.sections[index].distance, route.sections[index].seconds, 0)
            
            for kwh in fuel_kW_h:
                if kwh < 0:
                    section_battery = decrease_battery_charge(section_battery, kwh / bus.electric_engine_efficiency, bus.charge)

    elif section == 1:
        """
            (VSP (kW) * Section Time (h) -> Energy Required to travel the section (kWh)
        """
        if route.sections[index].bus_stop == 1:
            kW_h, _, _ = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
            route.sections[index].distance, route.sections[index].seconds, section)

            _, fuel_kW_h, _ = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
            route.sections[index].distance, route.sections[index].seconds, 0)

            for kwh in fuel_kW_h:
                if kwh < 0:
                    section_battery = section_battery - kwh / bus.electric_engine_efficiency#decrease_battery_charge(section_battery, kwh / bus.electric_engine_efficiency, bus.charge)
        else:
            kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
            0, bus.weight, bus.frontal_section) * route.sections[index].seconds/3600

            fuel_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
            0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

            for kwh in [fuel_kW_h]:
                if kwh < 0:
                    section_battery = decrease_battery_charge(section_battery, kwh / bus.electric_engine_efficiency, bus.charge)


        
        section_battery = kW_h / bus.electric_engine_efficiency
    
    cont = index
    '''if index < final_stop:
        while cont < final_stop:
            remaining_charges[cont] = bus.charge if remaining_charges[cont] + section_battery > bus.charge else remaining_charges[cont] + section_battery 
            cont += 1
    else:
        while cont < len(remaining_charges):
            remaining_charges[cont] = bus.charge if remaining_charges[cont] + section_battery > bus.charge else remaining_charges[cont] + section_battery 
            cont += 1'''



    return remaining_charges


def simple_evaluate(sol, route, bus):
    count = 0
    evaluation_array = []
    for section in route.sections:
        evaluation_array.append(sol[count] / 100)
        count += 1
    """ VSP Model application in order to obtain the objectives"""
    total_emissions = 0
    green_kms = 0
    remaining_charge = bus.charge
    section_battery = 0
    batteries = []
    green_kms_per_zone = []
    remaining_charges = []
    recharge = 0
    for index,section in enumerate(evaluation_array):
        kW_h = 0
        fuel_kW_h = 0
        battery_kW_h = 0
        section_emissions = 0
        section_green_kms = 0
        if section == 0:
            """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section (kWh)
            """
            if route.sections[index].bus_stop == 1:
                _, kW_h, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)
            else:

                kW_h = [vehicle_specific_power(route.sections[index].speed , route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * route.sections[index].seconds/3600]
            for kwh in kW_h:
                if kwh < 0:
                    gasoline_gallon_equivalent = 0
                    remaining_charge = decrease_battery_charge(remaining_charge, kwh / bus.electric_engine_efficiency, bus.charge)
                else:
                    gasoline_gallon_equivalent = kwh / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
            
                section_emissions += gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

            total_emissions += section_emissions

        elif section < 1:
            if route.sections[index].bus_stop == 0:
                if section < 0.50:
                    """
                        (VSP (kW) * Section Time (h) -> Energy Required to travel the section part with fuel (kWh)
                    """
                    fuel_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                    0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                    if fuel_kW_h < 0:
                        gasoline_gallon_equivalent = 0
                        remaining_charge = decrease_battery_charge(remaining_charge, fuel_kW_h / bus.electric_engine_efficiency, bus.charge)

                    else:
                        gasoline_gallon_equivalent = fuel_kW_h / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
                    
                    section_emissions = gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

                    total_emissions += section_emissions
                else:
                    """
                    (VSP (kW) * Section Time (h) -> Energy Required to travel the section part with battery (kWh)
                    """
                    battery_kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                    0, bus.weight, bus.frontal_section) * (route.sections[index].seconds/3600)

                    section_battery = battery_kW_h / bus.electric_engine_efficiency
                    section_green_kms = route.sections[index].distance

                    remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
                    green_kms += section_green_kms
            else:
                """
                    (VSP (kW) * Section Time (h) -> Energy Required to travel the section(kWh)
                """

                battery_kW_h, fuel_kW_h, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)

                section_battery = battery_kW_h / bus.electric_engine_efficiency
                section_green_kms = route.sections[index].distance * section

                for kwh in fuel_kW_h:
                    if kwh < 0:
                        gasoline_gallon_equivalent = 0
                        remaining_charge = decrease_battery_charge(remaining_charge, kwh / bus.electric_engine_efficiency, bus.charge)
                    else:
                        gasoline_gallon_equivalent = kwh / bus.fuel_engine_efficiency * 0.02635046113 # Conversion factor
                    
                    section_emissions += gasoline_gallon_equivalent * 10.180 # Kgs of CO2 emissions

                total_emissions += section_emissions
                remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
                green_kms += section_green_kms

        else:
            """
                (VSP (kW) * Section Time (h) -> Energy Required to travel the section (kWh)
            """
            if route.sections[index].bus_stop == 1:
                kW_h, _, recharge = acceleration_section_power(0, route.sections[index].speed, 0.7, route.sections[index].slope,
                route.sections[index].distance, route.sections[index].seconds, section)
            else:

                kW_h = vehicle_specific_power(route.sections[index].speed, route.sections[index].slope,
                0, bus.weight, bus.frontal_section) * route.sections[index].seconds/3600


            section_battery = kW_h / bus.electric_engine_efficiency
            section_green_kms = route.sections[index].distance

            remaining_charge = decrease_battery_charge(remaining_charge, section_battery, bus.charge)
            green_kms += section_green_kms
        
        #print("{} : {} ".format(route.sections[index].bus_stop, section))
        #print("{} , {} , {}".format(kW_h, battery_kW_h, fuel_kW_h))
        #input('')
        
        if (index + 1) >= len(route.sections) or route.sections[index + 1].bus_stop == 1:
            recharge = recharge / bus.electric_engine_efficiency * 0.5
            if remaining_charge + recharge > bus.charge:
                remaining_charge = bus.charge
            else:
                remaining_charge += recharge
            recharge = 0
        if  route.sections[index].final_stop == 1:
            remaining_charge = bus.charge

        batteries.append(section_battery)
        green_kms_per_zone.append(section_green_kms)
        remaining_charges.append(remaining_charge)
    return total_emissions, green_kms, remaining_charges, batteries


def main_get_solution_details(input_path, input_solution, CSV_filename, recharge):
    data = pd.read_csv(input_path, delimiter=None)
    data = get_solution_details(data, input_solution, input_path, CSV_filename, recharge)

if __name__ == "__main__":
    data = pd.read_csv(config_input_path, delimiter=None)
    data = get_solution_details(data, config_input_solution, config_input_path, config_input_surname, config_recharge)

