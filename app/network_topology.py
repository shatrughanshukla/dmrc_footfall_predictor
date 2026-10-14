"""
Real Delhi Metro network topology: station order along each line, and the
interchange (transfer) stations between lines.

Source: published DMRC route maps / line-by-line station orderings
(cross-checked against DMRC operational network information). The primary
routes plus LINE_SEGMENTS include operational extensions through 2026.

This is the piece that was completely missing from the original project:
DELHI_METRO_DATA.csv only ever had (Station, Line, Latitude, Longitude) -- no
sequence, no interchange info, and every station appeared on exactly one
line. Without this file there was no way to know which stations are
*adjacent*, so the old code fell back to straight-line distance between
every possible pair.

Each line is a simple ordered list -- consecutive entries are the stations
you actually ride between, in order.
"""

LINES = {
    "Red Line": [
        "Shaheed Sthal", "Hindon", "Arthala", "Mohan Nagar", "Shyam Park",
        "Major Mohit Sharma", "Raj Bagh", "Shaheed Nagar", "Dilshad Garden",
        "Jhilmil", "Mansarovar Park", "Shahdara", "Welcome", "Seelampur",
        "Shastri Park", "Kashmere Gate", "Tis Hazari", "Pul Bangash",
        "Pratap Nagar", "Shastri Nagar", "Inderlok", "Kanhaiya Nagar",
        "Keshav Puram", "Netaji Subhash Place", "Kohat Enclave", "Pitam Pura",
        "Rohini East", "Rohini West", "Rithala",
    ],
    "Yellow Line": [
        "Samaypur Badli", "Rohini Sector 18", "Haiderpur Badli Mor", "Jahangirpuri",
        "Adarsh Nagar", "Azadpur", "Model Town", "GTB Nagar", "Vishwa Vidyalaya",
        "Vidhan Sabha", "Civil Lines", "Kashmere Gate", "Chandni Chowk",
        "Chawri Bazar", "New Delhi", "Rajiv Chowk", "Patel Chowk",
        "Central Secretariat",
        "Udyog Bhawan", "Lok Kalyan Marg", "Jor Bagh", "INA", "AIIMS",
        "Green Park", "Hauz Khas", "Malviya Nagar", "Saket", "Qutab Minar",
        "Chhatarpur", "Sultanpur", "Ghitorni", "Arjan Garh", "Guru Dronacharya",
        "Sikandarpur", "MG Road", "IFFCO Chowk", "Millennium City Centre Gurugram",
    ],
    "Blue Line": [
        "Dwarka Sector 21", "Dwarka Sector 8", "Dwarka Sector 9",
        "Dwarka Sector 10", "Dwarka Sector 11", "Dwarka Sector 12",
        "Dwarka Sector 13", "Dwarka Sector 14", "Dwarka", "Dwarka Mor",
        "Nawada", "Uttam Nagar West", "Uttam Nagar East", "Janakpuri West",
        "Janakpuri East", "Tilak Nagar", "Subhash Nagar", "Tagore Garden",
        "Rajouri Garden", "Ramesh Nagar", "Moti Nagar", "Kirti Nagar",
        "Shadipur", "Patel Nagar", "Rajendra Place", "Karol Bagh",
        "Jhandewalan", "Ramakrishna Ashram Marg", "Rajiv Chowk",
        "Barakhambha Road", "Mandi House", "Supreme Court", "Indraprastha",
        "Yamuna Bank", "Akshardham", "Mayur Vihar -I", "Mayur Vihar Extension",
        "New Ashok Nagar", "Noida Sector 15", "Noida Sector 16",
        "Noida Sector 18", "Botanical Garden", "Golf Course",
        "Noida City Centre", "Noida Sector 34", "Noida Sector 52",
        "Noida Sector 61", "Noida Sector 59", "Noida Sector 62",
        "Noida Electronic City",
    ],
    "Blue Line branch": [
        "Yamuna Bank", "Laxmi Nagar", "Nirman Vihar", "Preet Vihar",
        "Karkarduma", "Anand Vihar ISBT", "Kaushambi", "Vaishali",
    ],
    "Green Line": [
        "Inderlok", "Kirti Nagar", "Ashok Park Main", "Punjabi Bagh",
        "Punjabi Bagh West", "Shivaji Park", "Madipur", "Paschim Vihar East",
        "Paschim Vihar West", "Peera Garhi", "Udyog Nagar",
        "Maharaja Surajmal Stadium", "Nangloi", "Nangloi Railway station",
        "Rajdhani Park", "Mundka", "Mundka Industrial Area", "Ghevra",
        "Tikri Kalan", "Tikri Border", "Pandit Shree Ram Sharma",
        "Bahadurgarh City", "Brigadier Hoshiyar Singh",
    ],
    "Green Line branch": [
        "Ashok Park Main", "Satguru Ramsingh Marg", "Kirti Nagar",
    ],
    "Violet Line": [
        "Kashmere Gate", "Lal Qila", "Jama Masjid", "Delhi Gate", "ITO",
        "Mandi House", "Janpath", "Central Secretariat", "Khan Market",
        "Jawaharlal Nehru Stadium", "Jangpura", "Lajpat Nagar", "Moolchand",
        "Kailash Colony", "Nehru Place", "Kalkaji Mandir", "Govind Puri",
        "Harkesh Nagar Okhla", "Jasola Apollo", "Sarita Vihar",
        "Mohan Estate", "Tughlakabad Station", "Badarpur Border", "Sarai",
        "NHPC Chowk", "Mewala Maharajpur", "Sector 28", "Badkhal Mor",
        "Old Faridabad", "Neelam Chowk Ajronda", "Bata Chowk",
        "Escorts Mujesar", "Sant Surdas (Sihi)", "Raja Nahar Singh",
    ],
    "Pink Line": [
        "Majlis Park", "Azadpur", "Shalimar Bagh", "Netaji Subhash Place",
        "Shakurpur", "Punjabi Bagh West", "ESI Hospital", "Rajouri Garden",
        "Mayapuri", "Naraina Vihar", "Delhi Cantonment",
        "Durgabai Deshmukh South Campus", "Sir Vishweshwaraiah Moti Bagh",
        "Bhikaji Cama Place", "Sarojini Nagar", "INA", "South",
        "Lajpat Nagar", "Vinobapuri", "Ashram", "Hazrat Nizamuddin",
        "Mayur Vihar -I", "Mayur Vihar Pocket I", "Trilokpuri Sanjay Lake",
        "East Vinod Nagar – Mayur Vihar-II", "Mandawali – West Vinod Nagar",
        "IP Extension", "Anand Vihar ISBT", "Karkarduma",
        "Karkarduma Court", "Krishna Nagar", "East Azad Nagar", "Welcome",
        "Jaffrabad", "Maujpur-Babarpur", "Gokulpuri", "Johari Enclave",
        "Shiv Vihar",
    ],
    "Magenta Line": [
        "Krishna Park Extension", "Janakpuri West", "Dabri Mor-Janakpuri South", "Dashrath Puri",
        "Palam", "Sadar Bazaar Cantonment", "Terminal 1-IGI Airport",
        "Shankar Vihar", "Vasant Vihar", "Munirka", "R.K.Puram",
        "Hauz Khas", "Panchsheel Park", "Chirag Delhi", "Greater Kailash",
        "Nehru Enclave", "Kalkaji Mandir", "Okhla NSIC", "Sukhdev Vihar",
        "Jamia Millia Islamia", "Okhla Vihar", "Jasola Vihar Shaheen Bagh",
        "Kalindi Kunj", "Okhla Bird Sanctuary", "Botanical Garden",
    ],
    "Grey Line": ["Dwarka", "Nangli", "Najafgarh"],
    "Orange Line": [
        "New Delhi", "Shivaji Stadium", "Dhaula Kuan", "Delhi Aerocity",
        "Indira Gandhi International Airport", "Dwarka Sector 21",
        "Yashobhoomi Dwarka Sector-25",
    ],
}

# Additional operational sections that share a corridor identity but are
# not consecutive with the primary route list above. Keeping these as separate
# ordered segments prevents accidentally connecting stations through unopened
# Phase IV alignments.
LINE_SEGMENTS = {
    "Pink Line": [[
        "Majlis Park", "Burari", "Jharoda Majra", "Jagatpur Village",
        "Soorghat", "Sonia Vihar", "Khajuri Khas", "Bhajanpura",
        "Yamuna Vihar", "Maujpur-Babarpur",
    ]],
    "Magenta Line": [[
        "Majlis Park", "Bhalaswa", "Haiderpur Badli Mor", "Haiderpur Village",
        "Uttari Pitampura-Prashant Vihar", "Madhuban Chowk", "Deepali Chowk",
    ]],
}


def line_route_segments():
    """Return every ordered operational route segment grouped by line."""
    segments = {line: [stops] for line, stops in LINES.items()}
    for line, additions in LINE_SEGMENTS.items():
        segments.setdefault(line, []).extend(additions)
    return segments

# station name (as it appears above) -> set of line keys it interchanges between.
# Only stations genuinely shared by 2+ operational routes are listed --
# Sikandarpur/Rapid Metro Gurgaon and Noida Sector 52/Aqua Line are real DMRC
# interchanges too, but those other networks aren't in this project's data.
INTERCHANGES = {
    "Kashmere Gate": {"Red Line", "Yellow Line", "Violet Line"},
    "Rajiv Chowk": {"Yellow Line", "Blue Line"},
    "Inderlok": {"Red Line", "Green Line"},
    "New Delhi": {"Yellow Line", "Orange Line"},
    "Central Secretariat": {"Yellow Line", "Violet Line"},
    "Dwarka Sector 21": {"Blue Line", "Orange Line"},
    "Kirti Nagar": {"Blue Line", "Green Line", "Green Line branch"},
    "Yamuna Bank": {"Blue Line", "Blue Line branch"},
    "Ashok Park Main": {"Green Line", "Green Line branch"},
    "Mandi House": {"Blue Line", "Violet Line"},
    "Azadpur": {"Yellow Line", "Pink Line"},
    "Netaji Subhash Place": {"Red Line", "Pink Line"},
    "Rajouri Garden": {"Blue Line", "Pink Line"},
    "INA": {"Yellow Line", "Pink Line"},
    "Lajpat Nagar": {"Violet Line", "Pink Line"},
    "Janakpuri West": {"Blue Line", "Magenta Line"},
    "Hauz Khas": {"Yellow Line", "Magenta Line"},
    "Kalkaji Mandir": {"Violet Line", "Magenta Line"},
    "Botanical Garden": {"Blue Line", "Magenta Line"},
    "Anand Vihar ISBT": {"Blue Line branch", "Pink Line"},
    "Karkarduma": {"Blue Line branch", "Pink Line"},
    "Welcome": {"Red Line", "Pink Line"},
    "Mayur Vihar -I": {"Blue Line", "Pink Line"},
    "Majlis Park": {"Pink Line", "Magenta Line"},
    "Haiderpur Badli Mor": {"Yellow Line", "Magenta Line"},
    "Dwarka": {"Blue Line", "Grey Line"},
    "Punjabi Bagh West": {"Green Line", "Pink Line"},
}

# Average interchange (platform-to-platform transfer) time in minutes.
# Real DMRC transfers range ~3-7 min depending on the station; Rajiv Chowk
# and Kashmere Gate run long. This is a network-wide average, not per-station.
INTERCHANGE_PENALTY_MIN = 5.0

# Fallback inter-station run+dwell time (minutes) used only when we can't
# compute one from coordinates (missing/placeholder lat-long -- see
# travel_graph.py). DMRC's scheduled average is close to this.
DEFAULT_SEGMENT_MIN = 2.5

# Manual alias map: topology name -> canonical name as it appears in
# DELHI_METRO_DATA.csv, for the handful that don't match after normalization.
ALIASES = {
    "rohini sector 18": "Rohini Sector 18",
    "vishwa vidyalaya": "Vishwa Vidyalaya",
    "barakhambha road": "Barakhambha Road",
    "supreme court": "Supreme Court",
    "sant surdas (sihi)": "Sant Surdas (Sihi)",
    "east vinod nagar – mayur vihar-ii": "East Vinod Nagar – Mayur Vihar-II",
    "mandawali – west vinod nagar": "Mandawali – West Vinod Nagar",
    "r.k.puram": "R.K.Puram",
    "indira gandhi international airport": "Indira Gandhi International Airport",
}
