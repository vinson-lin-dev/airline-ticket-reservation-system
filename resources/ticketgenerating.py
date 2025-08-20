# Configuration
airline_name = 'China Eastern'
flight_num = 104
number_of_tickets = 200
start_ticket_id = 800  # Ensure this is set to avoid duplicates
output_file = 'tickets_china_eastern_104.sql'

# Generate SQL Insert Statements
with open(output_file, 'w') as file:
    file.write("INSERT INTO `ticket` (`ticket_id`, `airline_name`, `flight_num`) VALUES\n")
    for i in range(number_of_tickets):
        ticket_id = start_ticket_id + i
        line = f"({ticket_id}, '{airline_name}', {flight_num})"
        if i < number_of_tickets - 1:
            line += ",\n"
        else:
            line += ";\n"
        file.write(line)

print(f"SQL insert statements for {number_of_tickets} tickets have been written to '{output_file}'.")
