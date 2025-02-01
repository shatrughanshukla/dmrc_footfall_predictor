import csv

# Data to be written to the CSV file
data = [
    ["Line", "No of Coaches", "Compartment Capacity", "Total Capacity"],
    ["Red Line", 8, 250, 8 * 250],
    ["Yellow Line", 6, 250, 6 * 250],
    ["Blue Line", 8, 310, 8 * 310],
    ["Green Line", 4, 240, 4 * 240],
    ["Violet Line", 6, 240, 6 * 240],
    ["Orange Line", 6, 326, 6 * 326],
    ["Pink Line", 6, 240, 6 * 240],
    ["Magenta Line", 6, 240, 6 * 240],
    ["Grey Line", 6, 240, 6 * 240]
]

# Create and write to the CSV file
with open('metro_lines.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerows(data)

print("CSV file 'metro_lines.csv' created successfully.")