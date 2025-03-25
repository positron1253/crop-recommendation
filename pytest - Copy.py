import streamlit as st
import pandas as pd
import numpy as np
import math
import uuid
from datetime import datetime
import json
import pickle
import os
from together import Together
from googletrans import Translator
from gtts import gTTS
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
# File paths for our "database"
FARMERS_FILE = "farmers.json"
VENDORS_FILE = "vendors.json"
COMMUNITIES_FILE = "communities.json"
MARKET_PRICES_FILE = "market_prices.json"
FARMING_TIPS_FILE = "farming_tips.json"
POLLS_FILE = "polls.json"  # New file for storing polls

# Initialize session state variables if they don't exist
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_user_type' not in st.session_state:
    st.session_state.current_user_type = None
if 'chat_community' not in st.session_state:
    st.session_state.chat_community = None
if 'view' not in st.session_state:
    st.session_state.view = "communities"  # Default view is communities list
if 'selected_poll' not in st.session_state:
    st.session_state.selected_poll = None

# Haversine formula to calculate distance between two points on Earth
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

# Database operations
def load_data(file_path):
    """Load data from JSON file"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_data(data, file_path):
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def register_user(user_type, name, latitude, longitude):
    """Register a new user (farmer or vendor)"""
    user_id = str(uuid.uuid4())
    user_data = {
        "id": user_id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "created_at": datetime.now().isoformat()
    }
    
    if user_type == "farmer":
        farmers = load_data(FARMERS_FILE)
        farmers.append(user_data)
        save_data(farmers, FARMERS_FILE)
        
        # Add farmer to all nearby vendor communities
        add_farmer_to_communities(user_data)
        
    else:  # vendor
        vendors = load_data(VENDORS_FILE)
        vendors.append(user_data)
        save_data(vendors, VENDORS_FILE)
        
        # Create a new community for this vendor
        create_vendor_community(user_data)
    
    return user_id

def create_vendor_community(vendor):
    """Create a new community for a vendor and add nearby farmers"""
    communities = load_data(COMMUNITIES_FILE)
    
    # Create new community
    community = {
        "id": str(uuid.uuid4()),
        "name": f"{vendor['name']}'s Community",
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "members": [{"id": vendor["id"], "name": vendor["name"], "type": "vendor"}],
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    
    # Add all farmers within 50km
    farmers = load_data(FARMERS_FILE)
    for farmer in farmers:
        distance = calculate_distance(
            vendor["latitude"], vendor["longitude"],
            farmer["latitude"], farmer["longitude"]
        )
        
        if distance <= 50:  # 50 km radius
            community["members"].append({
                "id": farmer["id"], 
                "name": farmer["name"],
                "type": "farmer",
                "distance": round(distance, 2)
            })
    
    communities.append(community)
    save_data(communities, COMMUNITIES_FILE)

def add_farmer_to_communities(farmer):
    """Add a new farmer to all vendor communities within 50km"""
    communities = load_data(COMMUNITIES_FILE)
    vendors = load_data(VENDORS_FILE)
    
    for community in communities:
        vendor_id = community["vendor_id"]
        vendor = next((v for v in vendors if v["id"] == vendor_id), None)
        
        if vendor:
            distance = calculate_distance(
                vendor["latitude"], vendor["longitude"],
                farmer["latitude"], farmer["longitude"]
            )
            
            if distance <= 50:  # 50 km radius
                community["members"].append({
                    "id": farmer["id"], 
                    "name": farmer["name"],
                    "type": "farmer",
                    "distance": round(distance, 2)
                })
    
    save_data(communities, COMMUNITIES_FILE)

def get_user_communities(user_id, user_type):
    """Get all communities that a user is a member of"""
    communities = load_data(COMMUNITIES_FILE)
    user_communities = []
    
    for community in communities:
        if any(member["id"] == user_id for member in community["members"]):
            community_info = {
                "id": community["id"],
                "name": community["name"],
                "vendor_name": community["vendor_name"],
                "member_count": len(community["members"]),
                "message_count": len(community["messages"])
            }
            user_communities.append(community_info)
    
    return user_communities

def add_message_to_community(community_id, user_id, user_name, user_type, message):
    """Add a message to a community chat"""
    communities = load_data(COMMUNITIES_FILE)
    
    for community in communities:
        if community["id"] == community_id:
            community["messages"].append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "user_name": user_name,
                "user_type": user_type,
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
    
    save_data(communities, COMMUNITIES_FILE)

def get_community_details(community_id):
    """Get detailed information about a community"""
    communities = load_data(COMMUNITIES_FILE)
    
    for community in communities:
        if community["id"] == community_id:
            return community
    
    return None

def get_user_by_id(user_id, user_type):
    """Get user details by ID"""
    if user_type == "farmer":
        users = load_data(FARMERS_FILE)
    else:
        users = load_data(VENDORS_FILE)
    
    for user in users:
        if user["id"] == user_id:
            return user
    
    return None

# Functions for polls
def create_poll(community_id, vendor_id, vendor_name, product, quantity, unit, deadline):
    """Create a new poll for a specific product requirement"""
    polls = load_data(POLLS_FILE)
    
    poll_id = str(uuid.uuid4())
    
    poll = {
        "id": poll_id,
        "community_id": community_id,
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "product": product,
        "quantity": quantity,
        "unit": unit,
        "deadline": deadline,
        "status": "open",  # open, fulfilled, or closed
        "created_at": datetime.now().isoformat(),
        "responses": []
    }
    
    polls.append(poll)
    save_data(polls, POLLS_FILE)
    
    # Add a message to the community about the new poll
    community = get_community_details(community_id)
    if community:
        message = f"I need {quantity} {unit} of {product} by {deadline}. Please respond on poll if you can contribute."
        add_message_to_community(
            community_id=community_id,
            user_id=vendor_id,
            user_name=vendor_name,
            user_type="vendor",
            message=message
        )
    
    return poll_id

def respond_to_poll(poll_id, farmer_id, farmer_name, quantity):
    """Respond to a poll with how much a farmer can contribute"""
    polls = load_data(POLLS_FILE)
    
    for poll in polls:
        if poll["id"] == poll_id:
            # Generate alphanumeric reference code
            reference_code = f"P{poll_id[:4]}-F{farmer_id[:4]}-{uuid.uuid4().hex[:6].upper()}"
            
            # Check if already responded
            existing_response = next((r for r in poll["responses"] if r["farmer_id"] == farmer_id), None)
            
            if existing_response:
                # Update existing response
                existing_response["quantity"] = quantity
                existing_response["updated_at"] = datetime.now().isoformat()
                # If reference code doesn't exist, generate one
                if "reference_code" not in existing_response:
                    existing_response["reference_code"] = reference_code
            else:
                # Add new response
                poll["responses"].append({
                    "farmer_id": farmer_id,
                    "farmer_name": farmer_name,
                    "quantity": quantity,
                    "reference_code": reference_code,
                    "created_at": datetime.now().isoformat()
                })
            
            # Check if poll is fulfilled
            total_quantity = sum(r["quantity"] for r in poll["responses"])
            if total_quantity >= poll["quantity"] and poll["status"] == "open":
                poll["status"] = "fulfilled"
                
                # Add message to community about fulfillment
                message = f"✅ Requirement for {poll['quantity']} {poll['unit']} of {poll['product']} has been met. Thank you to all farmers who contributed!"
                add_message_to_community(
                    community_id=poll["community_id"],
                    user_id=poll["vendor_id"],
                    user_name=poll["vendor_name"],
                    user_type="vendor",
                    message=message
                )
            
            save_data(polls, POLLS_FILE)
            return True
    
    return False

def close_poll(poll_id, vendor_id):
    """Close a poll (can only be done by the vendor who created it)"""
    polls = load_data(POLLS_FILE)
    
    for poll in polls:
        if poll["id"] == poll_id and poll["vendor_id"] == vendor_id:
            poll["status"] = "closed"
            
            # Add message to community about poll closure
            message = f"❌ The poll for {poll['quantity']} {poll['unit']} of {poll['product']} has been closed."
            add_message_to_community(
                community_id=poll["community_id"],
                user_id=vendor_id,
                user_name=poll["vendor_name"],
                user_type="vendor",
                message=message
            )
            
            save_data(polls, POLLS_FILE)
            return True
    
    return False

def delete_poll(poll_id, vendor_id):
    """Delete a poll (can only be done by the vendor who created it)"""
    polls = load_data(POLLS_FILE)
    
    # Find the poll index
    poll_index = None
    for i, poll in enumerate(polls):
        if poll["id"] == poll_id and poll["vendor_id"] == vendor_id:
            poll_index = i
            break
    
    if poll_index is not None:
        # Get poll details for notification
        poll = polls[poll_index]
        
        # Remove the poll
        removed_poll = polls.pop(poll_index)
        save_data(polls, POLLS_FILE)
        
        # Add message to community about poll deletion
        message = f"The poll for {removed_poll['quantity']} {removed_poll['unit']} of {removed_poll['product']} has been deleted."
        add_message_to_community(
            community_id=removed_poll["community_id"],
            user_id=vendor_id,
            user_name=removed_poll["vendor_name"],
            user_type="vendor",
            message=message
        )
        
        return True
    
    return False

def get_community_polls(community_id):
    """Get all polls for a specific community"""
    polls = load_data(POLLS_FILE)
    return [p for p in polls if p["community_id"] == community_id]

def get_poll_by_id(poll_id):
    """Get a specific poll by ID"""
    polls = load_data(POLLS_FILE)
    return next((p for p in polls if p["id"] == poll_id), None)

def get_user_active_polls(user_id, user_type, include_closed=False):
    """Get all active polls (and optionally closed polls) that a user has responded to or created"""
    polls = load_data(POLLS_FILE)
    user_polls = []
    
    for poll in polls:
        # Only include open or fulfilled polls by default, unless include_closed is True
        if poll["status"] != "closed" or include_closed:
            if user_type == "farmer":
                # Check if the farmer has responded to this poll
                responded = any(r["farmer_id"] == user_id for r in poll["responses"])
                if responded:
                    user_polls.append(poll)
            elif user_type == "vendor" and poll["vendor_id"] == user_id:
                # Add vendor's created polls
                user_polls.append(poll)
    
    return user_polls

def add_market_price(vendor_id, vendor_name, product, price, unit, location, notes=""):
    """Add a new market price entry"""
    market_prices = load_data(MARKET_PRICES_FILE)
    
    price_entry = {
        "id": str(uuid.uuid4()),
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "product": product,
        "price": price,
        "unit": unit,
        "location": location,
        "notes": notes,
        "timestamp": datetime.now().isoformat()
    }
    
    market_prices.append(price_entry)
    save_data(market_prices, MARKET_PRICES_FILE)
    return price_entry["id"]

def get_latest_market_prices(limit=20):
    """Get the latest market prices"""
    market_prices = load_data(MARKET_PRICES_FILE)
    
    # Sort by timestamp (newest first)
    sorted_prices = sorted(
        market_prices, 
        key=lambda x: x["timestamp"], 
        reverse=True
    )
    
    return sorted_prices[:limit]

def get_product_market_prices(product):
    """Get market prices for a specific product"""
    market_prices = load_data(MARKET_PRICES_FILE)
    
    # Filter by product name
    product_prices = [p for p in market_prices if p["product"].lower() == product.lower()]
    
    # Sort by timestamp (newest first)
    sorted_prices = sorted(
        product_prices, 
        key=lambda x: x["timestamp"], 
        reverse=True
    )
    
    return sorted_prices

def get_vendor_market_prices(vendor_id):
    """Get market prices posted by a specific vendor"""
    market_prices = load_data(MARKET_PRICES_FILE)
    
    # Filter by vendor ID
    vendor_prices = [p for p in market_prices if p["vendor_id"] == vendor_id]
    
    # Sort by timestamp (newest first)
    sorted_prices = sorted(
        vendor_prices, 
        key=lambda x: x["timestamp"], 
        reverse=True
    )
    
    return sorted_prices

# NEW FUNCTIONS FOR FARMING TIPS
def add_farming_tip(user_id, user_name, user_type, title, content, category):
    """Add a new farming tip or resource"""
    farming_tips = load_data(FARMING_TIPS_FILE)
    
    tip_entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": user_name,
        "user_type": user_type,
        "title": title,
        "content": content,
        "category": category,
        "likes": 0,
        "liked_by": [],
        "timestamp": datetime.now().isoformat()
    }
    
    farming_tips.append(tip_entry)
    save_data(farming_tips, FARMING_TIPS_FILE)
    return tip_entry["id"]

def like_farming_tip(tip_id, user_id):
    """Like a farming tip"""
    farming_tips = load_data(FARMING_TIPS_FILE)
    
    for tip in farming_tips:
        if tip["id"] == tip_id:
            if user_id not in tip["liked_by"]:
                tip["liked_by"].append(user_id)
                tip["likes"] = len(tip["liked_by"])
                save_data(farming_tips, FARMING_TIPS_FILE)
                return True
            return False
    
    return False

def get_all_farming_tips():
    """Get all farming tips and resources"""
    farming_tips = load_data(FARMING_TIPS_FILE)
    
    # Sort by likes (most liked first)
    sorted_tips = sorted(
        farming_tips, 
        key=lambda x: (x["likes"], x["timestamp"]), 
        reverse=True
    )
    
    return sorted_tips

def get_farming_tips_by_category(category):
    """Get farming tips for a specific category"""
    farming_tips = load_data(FARMING_TIPS_FILE)
    
    # Filter by category
    category_tips = [t for t in farming_tips if t["category"].lower() == category.lower()]
    
    # Sort by likes (most liked first)
    sorted_tips = sorted(
        category_tips, 
        key=lambda x: (x["likes"], x["timestamp"]), 
        reverse=True
    )
    
    return sorted_tips

# Streamlit app UI
# Apply custom CSS for better styling
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        font-family: 'Arial', sans-serif;
    }
    
    /* Sidebar styles */
    .user-info-box {
        background-color: #f0f8ff;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        border: 1px solid #b0c4de;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        color: #333333; 
    

</style>
""", unsafe_allow_html=True)

# Create initial data files if they don't exist
if not os.path.exists(FARMERS_FILE):
    save_data([], FARMERS_FILE)
if not os.path.exists(VENDORS_FILE):
    save_data([], VENDORS_FILE)
if not os.path.exists(COMMUNITIES_FILE):
    save_data([], COMMUNITIES_FILE)
if not os.path.exists(MARKET_PRICES_FILE):
    save_data([], MARKET_PRICES_FILE)
if not os.path.exists(FARMING_TIPS_FILE):
    save_data([], FARMING_TIPS_FILE)

# Initialize sample data for demo if empty
market_prices = load_data(MARKET_PRICES_FILE)
if not market_prices:
    sample_products = [
        {"product": "Tomatoes", "price": 25.50, "unit": "kg", "location": "Delhi"},
        {"product": "Potatoes", "price": 15.75, "unit": "kg", "location": "Mumbai"},
        {"product": "Rice", "price": 45.00, "unit": "kg", "location": "Kolkata"},
        {"product": "Wheat", "price": 30.25, "unit": "kg", "location": "Chennai"},
        {"product": "Onions", "price": 20.00, "unit": "kg", "location": "Bangalore"}
    ]
    
    # Add sample market prices (will be properly populated by vendors later)
    for item in sample_products:
        add_market_price(
            vendor_id="sample_vendor",
            vendor_name="Sample Vendor",
            product=item["product"],
            price=item["price"],
            unit=item["unit"],
            location=item["location"],
            notes="Sample data for demonstration"
        )

farming_tips = load_data(FARMING_TIPS_FILE)
if not farming_tips:
    sample_tips = [
        {
            "title": "Soil Preparation for Wheat",
            "content": "Wheat requires well-drained soil with a pH between 6.0 and 7.0. Before planting, prepare your soil by tilling to a depth of 15cm and incorporate organic matter. Conduct a soil test to ensure proper nutrient levels.",
            "category": "Soil Management"
        },
        {
            "title": "Effective Water Conservation Techniques",
            "content": "Implement drip irrigation to save water. Mulching can reduce evaporation by up to 70%. Consider collecting rainwater during monsoon season for use during dry periods.",
            "category": "Water Management"
        },
        {
            "title": "Integrated Pest Management for Rice",
            "content": "Monitor your rice fields regularly for pests. Introduce beneficial insects like ladybugs to control aphids. Rotate crops annually to break pest cycles. Apply neem-based solutions as a natural pesticide.",
            "category": "Pest Control"
        }
    ]
    
    # Add sample farming tips
    for tip in sample_tips:
        add_farming_tip(
            user_id="sample_user",
            user_name="Agricultural Expert",
            user_type="vendor",
            title=tip["title"],
            content=tip["content"],
            category=tip["category"]
        )

# Sidebar with login, registration, and user info
with st.sidebar:
    st.header("User Panel")
    
    if st.session_state.current_user:
        user = get_user_by_id(st.session_state.current_user, st.session_state.current_user_type)
        
        # User info box with better styling
        st.markdown(
            f"""
            <div class="user-info-box">
                <div class="user-info-name">👤 {user['name']}</div>
                <div>Role: {st.session_state.current_user_type.capitalize()}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Create a styled logout button
        if st.button("Logout", key="logout_button", help="Log out of your account", use_container_width=True):
            st.session_state.current_user = None
            st.session_state.current_user_type = None
            st.session_state.chat_community = None
            st.session_state.view = "communities"
            st.rerun()
        
        # Apply custom styling to the logout button
        st.markdown(
            """
            <style>
            .element-container:has(button#logout_button) button {
                background-color: #e74c3c !important;
                color: white !important;
                border: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Navigation menu
        st.subheader("Navigation")
        st.write(" ")
        
        if st.button("Communities", use_container_width=True):
            st.session_state.view = "communities"
            st.session_state.chat_community = None
            st.rerun()
        
        # Add My Active Polls button in sidebar for both farmers and vendors
        if st.button("Supply Commitments", use_container_width=True):
            st.session_state.view = "supply_commitments"
            st.rerun()
            
        if st.button("Market Prices", use_container_width=True):
            st.session_state.view = "market_prices"
            st.rerun()
            
        if st.button("Farming Tips", use_container_width=True):
            st.session_state.view = "farming_tips"
            st.rerun()
        if st.session_state.current_user_type == "farmer":
            if st.button("crop Prediction", use_container_width=True):
                st.session_state.view = "crop_prediction"
                st.rerun()

            
        # Additional menu options for chat
        if st.session_state.view == "chat" and st.session_state.chat_community:
            if st.button("Back to Communities", use_container_width=True):
                st.session_state.view = "communities"
                st.session_state.chat_community = None
                st.rerun()
    else:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.subheader("Login")
            login_type = st.selectbox("I am a:", ["Farmer", "Vendor"], key="login_type")
            
            users = load_data(FARMERS_FILE if login_type.lower() == "farmer" else VENDORS_FILE)
            user_names = [user["name"] for user in users]
            
            if user_names:
                selected_name = st.selectbox("Select your name:", user_names)
                selected_user = next((user for user in users if user["name"] == selected_name), None)
                
                if st.button("Login") and selected_user:
                    st.session_state.current_user = selected_user["id"]
                    st.session_state.current_user_type = login_type.lower()
                    st.rerun()
            else:
                st.info(f"No {login_type.lower()}s registered yet. Please register first.")
        
        with tab2:
            st.subheader("Register")
            reg_type = st.selectbox("I am a:", ["Farmer", "Vendor"], key="reg_type")
            name = st.text_input("Your Name")
            
            # For demo purposes, using a map would be better in a real app
            col1, col2 = st.columns(2)
            with col1:
                latitude = st.number_input("Latitude", value=28.6139, format="%.4f")
            with col2:
                longitude = st.number_input("Longitude", value=77.2090, format="%.4f")
            
            if st.button("Register") and name:
                user_id = register_user(reg_type.lower(), name, latitude, longitude)
                st.session_state.current_user = user_id
                st.session_state.current_user_type = reg_type.lower()
                st.success("Registration successful!")
                st.rerun()

# Main content area - Show different views based on login status
if not st.session_state.current_user:
    st.info("Please login or register to use the app")
    
    # Display only registered users data without market prices or app features
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Registered Farmers")
        farmers = load_data(FARMERS_FILE)
        if farmers:
            farmer_df = pd.DataFrame([{
                "Name": farmer["name"],
                "Location": f"{farmer['latitude']:.4f}, {farmer['longitude']:.4f}"
            } for farmer in farmers])
            st.dataframe(farmer_df)
        else:
            st.write("No farmers registered yet")
    
    with col2:
        st.subheader("Registered Vendors")
        vendors = load_data(VENDORS_FILE)
        if vendors:
            vendor_df = pd.DataFrame([{
                "Name": vendor["name"],
                "Location": f"{vendor['latitude']:.4f}, {vendor['longitude']:.4f}"
            } for vendor in vendors])
            st.dataframe(vendor_df)
        else:
            st.write("No vendors registered yet")

else:
    # User is logged in
    user = get_user_by_id(st.session_state.current_user, st.session_state.current_user_type)
    
    # View management
    if st.session_state.view == "communities":
        # Communities List View
        st.subheader("My Communities")
        user_communities = get_user_communities(st.session_state.current_user, st.session_state.current_user_type)
        
        if user_communities:
            st.divider()
            for i, community in enumerate(user_communities):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{community['name']}**")
                    st.write(f"Vendor: {community['vendor_name']} • Members: {community['member_count']} • Messages: {community['message_count']}")
                with col2:
                    if st.button("Open Chat", key=f"chat_{community['id']}"):
                        st.session_state.chat_community = community['id']
                        st.session_state.view = "chat"
                        st.rerun()
                
                # Only add divider if it's not the last community
                if i < len(user_communities) - 1:
                    st.divider()
        
    
    elif st.session_state.view == "supply_commitments":
        # My Active Polls View (for both farmers and vendors)
        st.subheader("Active Commitments")
        st.write("")
        st.write("")
        # Get all communities to display names - Move this outside of any conditional blocks
        communities = load_data(COMMUNITIES_FILE)
        
        # Get active polls for the current user
        user_polls = get_user_active_polls(st.session_state.current_user, st.session_state.current_user_type)
        
        if user_polls:
            for poll in user_polls:
                # Get community name
                community = next((c for c in communities if c["id"] == poll["community_id"]), None)
                community_name = community["name"] if community else "Unknown Community"
                
                with st.container(border=True):
                    # Poll header
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{poll['product']}**: {poll['quantity']} {poll['unit']} by {poll['deadline']}")
                        st.write(f"Community: {community_name}")
                    with col2:
                        if poll["status"] == "fulfilled":
                            st.success("✅ Fulfilled")
                        elif poll["status"] == "closed":
                            st.error("❌ Closed")
                        else:
                            st.warning("⏳ Open")
                    
                    # Progress bar
                    total_committed = sum(r["quantity"] for r in poll["responses"])
                    percent_complete = min(100, round((total_committed / poll["quantity"]) * 100))
                    st.progress(percent_complete / 100)
                    st.write(f"Progress: {total_committed} of {poll['quantity']} {poll['unit']} ({percent_complete}%)")
                    
                    # Different information for farmers vs vendors
                    if st.session_state.current_user_type == "farmer":
                        # Find the farmer's response
                        farmer_response = next((r for r in poll["responses"] if r["farmer_id"] == st.session_state.current_user), None)
                        if farmer_response:
                            # Display complete farmer's contribution details
                            st.divider()
                            st.subheader("Your Response Details")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Your commitment:** {farmer_response['quantity']} {poll['unit']}")
                                st.write(f"**Reference Code:** {farmer_response.get('reference_code', 'N/A')}")
                                st.write(f"**Response Date:** {farmer_response['created_at'].split('T')[0]}")
                            with col2:
                                st.write(f"**Vendor:** {poll['vendor_name']}")
                                st.write(f"**Product:** {poll['product']}")
                                st.write(f"**Deadline:** {poll['deadline']}")
                            
                            # Instructions for delivery/reference code use
                            st.info("Keep this reference code handy when delivering your produce. The vendor will use this code to verify your commitment.")
                    else:  # vendor
                        # Show responder information with enhanced details
                        if poll["responses"]:
                            st.write(f"Responses: {len(poll['responses'])}")
                            
                            # Show response details in expanded table
                            with st.expander("View Detailed Responses", expanded=True):
                                # Create a more detailed dataframe with all information
                                response_df = pd.DataFrame([{
                                    "Farmer": r["farmer_name"],
                                    "Quantity": f"{r['quantity']} {poll['unit']}",
                                    "Reference Code": r.get("reference_code", "N/A"),
                                    "Response Date": r["created_at"].split('T')[0],
                                    "% of Total": f"{round((r['quantity'] / poll['quantity']) * 100, 1)}%"
                                } for r in poll["responses"]])
                                st.dataframe(response_df, use_container_width=True)
                                
                                # Summary statistics
                                st.write("**Summary:**")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Responses", len(poll["responses"]))
                                with col2:
                                    st.metric("Total Committed", f"{total_committed} {poll['unit']}")
                                with col3:
                                    remaining = max(0, poll["quantity"] - total_committed)
                                    st.metric("Still Needed", f"{remaining} {poll['unit']}")
                                
                            # Poll management options
                            col1, col2 = st.columns(2)
                            with col1:
                                if poll["status"] != "closed" and st.button("Close Poll", key=f"close_{poll['id']}"):
                                    if close_poll(poll["id"], st.session_state.current_user):
                                        st.success("Poll closed successfully!")
                                        st.rerun()
                            with col2:
                                if st.button("Delete Poll", key=f"delete_{poll['id']}"):
                                    if delete_poll(poll["id"], st.session_state.current_user):
                                        st.success("Poll deleted successfully!")
                                        st.rerun()
                        else:
                            st.info("No responses yet")
        else:
            if st.session_state.current_user_type == "farmer":
                st.info("You don't have any supply commitments yet..")
            else:
                st.info("You haven't created any active polls yet.")
        
        # Show closed polls in a separate section
        if st.session_state.current_user_type == "vendor":
            st.divider()
            st.subheader("Closed & Fulfilled Polls")
            st.write(" ")
            
            # Load all polls and filter for this vendor's closed polls
            all_polls = load_data(POLLS_FILE)
            closed_polls = [p for p in all_polls if p["vendor_id"] == st.session_state.current_user and p["status"] in ["closed", "fulfilled"]]
            
            if closed_polls:
                for poll in closed_polls:
                    # Get community name
                    community = next((c for c in communities if c["id"] == poll["community_id"]), None)
                    community_name = community["name"] if community else "Unknown Community"
                    
                    with st.expander(f"{poll['product']}: {poll['quantity']} {poll['unit']} - {poll['status'].upper()}"):
                        st.write(f"Community: {community_name}")
                        st.write(f"Deadline was: {poll['deadline']}")
                        
                        # Response information
                        if poll["responses"]:
                            response_df = pd.DataFrame([{
                                "Farmer": r["farmer_name"],
                                "Quantity": f"{r['quantity']} {poll['unit']}",
                                "Reference Code": r.get("reference_code", "N/A"),
                                "Response Date": r["created_at"].split('T')[0]
                            } for r in poll["responses"]])
                            st.dataframe(response_df, use_container_width=True)
                        else:
                            st.info("No responses were received for this poll.")
            else:
                st.info("You don't have any closed or fulfilled polls yet.")

        elif st.session_state.current_user_type == "farmer":
            st.divider()
            st.subheader("Past Commitments")
            st.write(" ")
            st.write(" ")
            # Get all polls and filter for this farmer's closed polls
            closed_polls = get_user_active_polls(st.session_state.current_user, "farmer", include_closed=True)
            closed_polls = [p for p in closed_polls if p["status"] == "closed"]
            
            if closed_polls:
                for poll in closed_polls:
                    # Get community name
                    community = next((c for c in communities if c["id"] == poll["community_id"]), None)
                    community_name = community["name"] if community else "Unknown Community"
                    
                    with st.expander(f"{poll['product']}: {poll['quantity']} {poll['unit']} - CLOSED"):
                        st.write(f"Community: {community_name}")
                        st.write(f"Vendor: {poll['vendor_name']}")
                        st.write(f"Deadline was: {poll['deadline']}")
                        
                        # Find the farmer's response
                        farmer_response = next((r for r in poll["responses"] if r["farmer_id"] == st.session_state.current_user), None)
                        if farmer_response:
                            # Display farmer's contribution details
                            st.divider()
                            st.subheader("Your Contribution Details")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Your commitment:** {farmer_response['quantity']} {poll['unit']}")
                                st.write(f"**Reference Code:** {farmer_response.get('reference_code', 'N/A')}")
                                st.write(f"**Response Date:** {farmer_response['created_at'].split('T')[0]}")
                            with col2:
                                st.write(f"**Total Required:** {poll['quantity']} {poll['unit']}")
                                total_committed = sum(r["quantity"] for r in poll["responses"])
                                st.write(f"**Total Committed:** {total_committed} {poll['unit']}")
                                st.write(f"**Your Percentage:** {round((farmer_response['quantity'] / poll['quantity']) * 100, 1)}%")
            else:
                st.info("You haven't contributed to any closed polls yet.")





    elif st.session_state.view == "crop_prediction":
        st.header("Crop View") 
        INDIAN_LANGUAGES = {
    "Hindi": "hi",
    "Bengali": "bn", 
    "Telugu": "te",
    "Marathi": "mr",
    "Tamil": "ta",
    "Urdu": "ur",
    "Gujarati": "gu",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Odia": "or",
    "Punjabi": "pa"
}       
        selected_language = st.selectbox(
                "Select Target Language:", 
                list(INDIAN_LANGUAGES.keys())

    )
        lang_code = INDIAN_LANGUAGES[selected_language]
        st.write(lang_code)
        feature_names=[
            'N', 
            'P',
            'K',
            'temperature', 
            'humidity', 
            'ph', 
            'rainfall'
        ]
        input_types=[
            'float',  # Temperature
            'float',  # Humidity
            'float',  # Pressure
            'float',  # Wind Speed
            'float',  # Rainfall
            'float',
            'float'  # Altitude
        ]
        cols = st.columns(2)
        input_values = []

        for i, (name, input_type) in enumerate(zip(feature_names,input_types)):
           
            col = cols[i % 2]
            
            with col:
                # Different input types
                if input_type == 'int':
                    value = st.number_input(
                        name, 
                        min_value=0, 
                        value=0, 
                        step=1, 
                        key=f"input_{i}"
                    )
                elif input_type == 'float':
                    value = st.number_input(
                        name, 
                        value=0.0, 
                        step=0.1, 
                        format="%.2f", 
                        key=f"input_{i}"
                    )
                elif input_type == 'categorical':
                    # Placeholder for categorical input
                    value = st.selectbox(
                        name, 
                        options=['Option 1', 'Option 2', 'Option 3'], 
                        key=f"input_{i}"
                    )
                else:
                    # Default to float
                    value = st.number_input(
                        name, 
                        value=0.0, 
                        step=0.1, 
                        format="%.2f", 
                        key=f"input_{i}"
                    )
                input_values.append(value)
        if st.button("Make Prediction"):
            try:
                with open('RandomForest.pkl', 'rb') as f:
                    model = pickle.load(f)
                
            except Exception as e:
                st.error(f"Error loading model: {e}")
                model = None
            try:
                with open('label_encoder.pkl', 'rb') as f:
                    decoder = pickle.load(f)
            except Exception as e:
                st.error(f"Error loading decoder: {e}")
                decoder = None

            if model and decoder:
                
            
                try:
                    # Convert input to numpy array
                    input_array = np.array(input_values).reshape(1, -1)
                    
                    # Make prediction
                    if hasattr(model, 'predict_proba'):
                        # If model supports probability prediction
                        prediction = model.predict(input_array)[0]
                        st.write(prediction)
                        prediction_label = decoder.inverse_transform([prediction])[0]
                        st.header(f"Predicted Crop: {prediction_label}")
                        probabilities = model.predict_proba(input_array)[0]
                        

                except Exception as e:
                        st.error(f"Prediction error: {e}")

                st.header("Prediction Results")
                
                # Create columns for result display
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Predicted Output", str(prediction))
                
                # Probability visualization if available
                if probabilities is not None:
                    with col2:
                        st.metric("Confidence", f"{max(probabilities):.2%}")
                    
                    # Probability distribution plot
                    fig = go.Figure(data=[
                        go.Bar(
                            x=[f'Class {i}' for i in range(len(probabilities))],
                            y=probabilities,
                            text=[f'{p:.2%}' for p in probabilities],
                            textposition='auto'
                        )
                    ])
                    fig.update_layout(
                        title='Class Probability Distribution',
                        xaxis_title='Classes',
                        yaxis_title='Probability',
                        yaxis_range=[0, 1]
                    )
                    st.plotly_chart(fig)

                str2= "Provide a detailed guide on how to grow " + str(prediction_label) + " including specific treatments, preventative measures, and any relevant environmental factors."
                client = Together(api_key=(''))

                response = client.chat.completions.create(
                    model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    messages=[{"role": "user", "content": str2}],
                    max_tokens=512,
                    temperature=0.7

                )
                print(response.choices[0].message.content)
                result = ''
                for choice in response.choices:
                    result += choice.message.content
                result = result.replace("*", "")
                
                
                INDIAN_LANGUAGES = {
    "Hindi": "hi",
    "Bengali": "bn", 
    "Telugu": "te",
    "Marathi": "mr",
    "Tamil": "ta",
    "Urdu": "ur",
    "Gujarati": "gu",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Odia": "or",
    "Punjabi": "pa"
}

                translator = Translator()
                lang_code = INDIAN_LANGUAGES[selected_language]
                translation = translator.translate(result, dest=lang_code)
                translated_text = translation.text

                st.header(translated_text)
                tts = gTTS(text=translated_text, lang=lang_code)
                # audio_buffer = BytesIO()
                # tts.write_to_fp(audio_buffer)
                tts.save("translated_audio.mp3")
                # with open(audio_buffer, 'rb') as audio:
                st.audio("translated_audio.mp3", format='audio/mp3')
                
           
    elif st.session_state.view == "chat" and st.session_state.chat_community:
        # Chat View
        community = get_community_details(st.session_state.chat_community)
        
        if community:
            # Chat header with tabs
            chat_tab, polls_tab = st.tabs(["Chat Messages", "Community Polls"])
            
            with chat_tab:
                st.subheader(f"Chat: {community['name']}")
                
                # Display community info in expander
                with st.expander("Community Details"):
                    st.write(f"Vendor: **{community['vendor_name']}**")
                    
                    # Display members
                    st.write(f"**Members ({len(community['members'])})**")
                    
                    # Group members by type
                    vendors = [m for m in community['members'] if m['type'] == 'vendor']
                    farmers = [m for m in community['members'] if m['type'] == 'farmer']
                    
                    st.write(f"Vendor: {vendors[0]['name']}")
                    st.write(f"Farmers: {len(farmers)}")
                    
                    # Show a sample of farmers with their distances
                    if farmers:
                        farmer_df = pd.DataFrame([{
                            "Name": f["name"],
                            "Distance (km)": f.get("distance", "N/A")
                        } for f in farmers[:5]])  # Show only 5 farmers for brevity
                        
                        st.dataframe(farmer_df)
                        if len(farmers) > 5:
                            st.write(f"...and {len(farmers) - 5} more farmers")
                
                # Display chat messages with improved styling and scrollable container
                st.divider()
                chat_container = st.container(height=500, border=True)
                
                with chat_container:
                    for msg in community['messages']:
                        is_self = msg['user_id'] == st.session_state.current_user
                        
                        # Format message based on sender with more visible colors and spacing
                        if is_self:
                            st.markdown(f"""
                            <div style='display: flex; justify-content: flex-end; margin-bottom: 20px;'>
                                <div style='background-color: #007BFF; color: white; padding: 12px; border-radius: 15px; max-width: 80%;'>
                                    <p style='margin: 0; text-align: right;'>{msg['content']}</p>
                                    <p style='margin: 0; font-size: 0.8em; color: #E6F2FF; text-align: right; margin-top: 5px;'>You - {msg['timestamp'].split('T')[1][:5]}</p>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # For messages from others
                            # Choose color based on user type - ensuring good contrast for text
                            if msg['user_type'] == 'farmer':
                                badge_bg = '#28a745'  # green
                                badge_text = 'white'
                                msg_bg = '#f1f1f1'    # light gray
                                msg_text = '#333333'  # dark gray
                            else:  # vendor
                                badge_bg = '#ffc107'  # yellow
                                badge_text = 'black'
                                msg_bg = '#f8f9fa'    # off-white
                                msg_text = '#333333'  # dark gray
                            
                            msg_type_badge = f"<span style='background-color: {badge_bg}; color: {badge_text}; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-right: 5px;'>{msg['user_type'].upper()}</span>"
                            
                            st.markdown(f"""
                            <div style='display: flex; justify-content: flex-start; margin-bottom: 20px;'>
                                <div style='background-color: {msg_bg}; color: {msg_text}; padding: 12px; border-radius: 15px; max-width: 80%;'>
                                    <p style='margin: 0; font-weight: bold;'>{msg_type_badge} {msg['user_name']}</p>
                                    <p style='margin: 0;'>{msg['content']}</p>
                                    <p style='margin: 0; font-size: 0.8em; color: #777; margin-top: 5px;'>{msg['timestamp'].split('T')[0]} {msg['timestamp'].split('T')[1][:5]}</p>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Input for new message
                st.divider()
                chat_msg = st.chat_input("Type a message...")
                if chat_msg:
                    add_message_to_community(
                        community_id=community['id'],
                        user_id=st.session_state.current_user,
                        user_name=user['name'],
                        user_type=st.session_state.current_user_type,
                        message=chat_msg
                    )
                    st.rerun()
            
            with polls_tab:
                # st.subheader("Community Polls")
                
                # Get polls for this community
                community_polls = get_community_polls(community['id'])
                
                # Display create poll form for vendors
                if st.session_state.current_user_type == "vendor" and community['vendor_id'] == st.session_state.current_user:
                    st.subheader("Create New Poll")
                    
                    with st.form("create_poll_form"):
                        poll_product = st.text_input("Product Name")
                        col1, col2 = st.columns(2)
                        with col1:
                            poll_quantity = st.number_input("Quantity Needed", min_value=1, step=1)
                        with col2:
                            poll_unit = st.selectbox("Unit", ["kg", "quintal", "ton", "pieces", "bundles"])
                        poll_deadline = st.date_input("Deadline")
                        
                        submit_poll = st.form_submit_button("Create Poll")
                        
                        if submit_poll and poll_product:
                            create_poll(
                                community_id=community['id'],
                                vendor_id=st.session_state.current_user,
                                vendor_name=user['name'],
                                product=poll_product,
                                quantity=poll_quantity,
                                unit=poll_unit,
                                deadline=poll_deadline.strftime("%Y-%m-%d")
                            )
                            st.success("Poll created successfully!")
                            st.rerun()
                
                # Display all polls
                st.subheader("Active Polls")
                
                # Filter active polls
                active_polls = [p for p in community_polls if p['status'] != 'closed']
                
                if active_polls:
                    for poll in active_polls:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"**{poll['product']}**: {poll['quantity']} {poll['unit']} by {poll['deadline']}")
                            with col2:
                                if poll['status'] == 'fulfilled':
                                    st.success("✅ Fulfilled")
                                else:
                                    st.warning("⏳ Open")
                            
                            # Progress bar
                            total_committed = sum(r['quantity'] for r in poll['responses'])
                            percent_complete = min(100, round((total_committed / poll['quantity']) * 100))
                            st.progress(percent_complete / 100)
                            st.write(f"Progress: {total_committed} of {poll['quantity']} {poll['unit']} ({percent_complete}%)")
                            
                            # Allow farmers to respond to open polls
                            if st.session_state.current_user_type == "farmer" and poll['status'] == 'open':
                                # Check if farmer has already responded
                                farmer_response = next((r for r in poll['responses'] if r['farmer_id'] == st.session_state.current_user), None)
                                
                                current_quantity = 0
                                if farmer_response:
                                    current_quantity = farmer_response['quantity']
                                    st.write(f"Your current commitment: {current_quantity} {poll['unit']}")
                                
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    farmer_quantity = st.number_input(
                                        "I can provide (quantity):", 
                                        min_value=0, 
                                        value=current_quantity,
                                        step=1,
                                        key=f"input_{poll['id']}"
                                    )
                                with col2:
                                    if st.button("Submit", key=f"submit_{poll['id']}"):
                                        if respond_to_poll(
                                            poll_id=poll['id'],
                                            farmer_id=st.session_state.current_user,
                                            farmer_name=user['name'],
                                            quantity=farmer_quantity
                                        ):
                                            st.success("Response submitted successfully!")
                                            st.rerun()
                                
                                # Show response details if already responded
                                if farmer_response and "reference_code" in farmer_response:
                                    st.info(f"Reference Code: **{farmer_response['reference_code']}**")
                else:
                    st.info("No active polls in this community")
                
                # Display closed polls in expander
                closed_polls = [p for p in community_polls if p['status'] == 'closed']
                if closed_polls:
                    with st.expander("Show Closed Polls"):
                        for poll in closed_polls:
                            st.write(f"**{poll['product']}**: {poll['quantity']} {poll['unit']} (Deadline: {poll['deadline']})")
                            st.write(f"Status: Closed • Responses: {len(poll['responses'])}")
                            st.divider()
    
    elif st.session_state.view == "market_prices":
        # Market Prices View
        st.subheader("Agricultural Market Prices")
        
        # Tabs for different views of market prices
        price_tab1, price_tab2 = st.tabs(["Browse Prices", "Add New Price"])
        
        with price_tab1:
            # Filter options
            st.write("Filter market prices by:")
            filter_col1, filter_col2 = st.columns(2)
            
            with filter_col1:
                filter_option = st.selectbox(
                    "Filter by:",
                    ["Latest Prices", "By Product", "By Location"]
                )
            
            with filter_col2:
                if filter_option == "By Product":
                    all_prices = load_data(MARKET_PRICES_FILE)
                    products = sorted(list(set(price["product"] for price in all_prices)))
                    selected_product = st.selectbox("Select Product:", products) if products else "No products available"
                elif filter_option == "By Location":
                    all_prices = load_data(MARKET_PRICES_FILE)
                    locations = sorted(list(set(price["location"] for price in all_prices)))
                    selected_location = st.selectbox("Select Location:", locations) if locations else "No locations available"
            
            # Display prices based on filter
            st.divider()
            if filter_option == "Latest Prices":
                prices = get_latest_market_prices(20)
            elif filter_option == "By Product" and products:
                prices = get_product_market_prices(selected_product)
            elif filter_option == "By Location" and locations:
                prices = [p for p in load_data(MARKET_PRICES_FILE) if p["location"] == selected_location]
                prices = sorted(prices, key=lambda x: x["timestamp"], reverse=True)
            else:
                prices = []
            
            if prices:
                price_df = pd.DataFrame([{
                    "Product": price["product"],
                    "Price (₹)": price["price"],
                    "Unit": price["unit"],
                    "Location": price["location"],
                    "Vendor": price["vendor_name"],
                    "Date": price["timestamp"].split('T')[0],
                    "Notes": price["notes"]
                } for price in prices])
                
                st.dataframe(price_df, use_container_width=True)
                
                # Plot price trends for products if filtered by product
                if filter_option == "By Product" and len(prices) > 1:
                    st.subheader(f"Price Trend for {selected_product}")
                    
                    # Get price history data
                    price_history = [{
                        "date": datetime.fromisoformat(p["timestamp"]).strftime("%Y-%m-%d"),
                        "price": p["price"]
                    } for p in prices]
                    
                    # Sort by date
                    price_history = sorted(price_history, key=lambda x: x["date"])
                    
                    # Create DataFrame for charting
                    history_df = pd.DataFrame(price_history)
                    
                    # Plot
                    st.line_chart(history_df.set_index("date"))
            else:
                st.info("No market prices available for the selected filter")
        
        with price_tab2:
            # Only vendors can add market prices
            if st.session_state.current_user_type == "vendor":
                st.write("Add a new market price entry to share with farmers")
                
                with st.form(key="price_form"):
                    price_col1, price_col2 = st.columns(2)
                    
                    with price_col1:
                        product = st.text_input("Product Name")
                        price = st.number_input("Price (₹)", min_value=0.0, format="%.2f")
                        unit = st.selectbox("Unit", ["kg", "quintal", "ton", "piece", "dozen", "bundle"])
                    
                    with price_col2:
                        location = st.text_input("Market Location")
                        notes = st.text_area("Additional Notes (optional)")
                    
                    submit_price = st.form_submit_button("Add Market Price")
                    
                    if submit_price and product and price > 0 and location:
                        add_market_price(
                            vendor_id=st.session_state.current_user,
                            vendor_name=user['name'],
                            product=product,
                            price=price,
                            unit=unit,
                            location=location,
                            notes=notes
                        )
                        st.success(f"Market price for {product} added successfully!")
                        st.rerun()
            else:
                st.info("Only vendors can add market prices. If you're a farmer, you can browse the latest prices.")

    elif st.session_state.view == "farming_tips":
        # Farming Tips and Resources View
        st.subheader("Farming Tips & Resources")
        
        # Tabs for different views of farming tips
        tip_tab1, tip_tab2 = st.tabs(["Browse Tips", "Add New Tip"])
        
        with tip_tab1:
            # Filter options
            st.write("Filter farming tips by:")
            
            categories = ["All Categories", "Soil Management", "Water Management", "Pest Control", 
                        "Crop Selection", "Harvesting", "Equipment", "Weather", "Sustainable Practices"]
            
            selected_category = st.selectbox("Category:", categories)
            
            st.divider()
            
            # Get tips based on filter
            if selected_category == "All Categories":
                tips = get_all_farming_tips()
            else:
                tips = get_farming_tips_by_category(selected_category)
            
            if tips:
                for tip in tips:
                    with st.container(border=True):
                        # Header with title and metadata
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"#### {tip['title']}")
                            st.caption(f"Posted by: {tip['user_name']} ({tip['user_type'].capitalize()}) • Category: {tip['category']} • {tip['timestamp'].split('T')[0]}")
                        
                        with col2:
                            # Like button functionality
                            likes_text = f"❤️ {tip['likes']}" 
                            
                            # Check if user already liked this tip
                            user_liked = st.session_state.current_user in tip["liked_by"]
                            like_button_text = "Liked" if user_liked else "Like"
                            
                            if st.button(like_button_text, key=f"like_{tip['id']}", disabled=user_liked):
                                success = like_farming_tip(tip['id'], st.session_state.current_user)
                                if success:
                                    st.success("Tip liked!")
                                    st.rerun()
                            
                            st.write(likes_text)
                        
                        # Tip content
                        st.markdown(tip['content'])
            else:
                if selected_category == "All Categories":
                    st.info("No farming tips available yet. Be the first to share knowledge!")
                else:
                    st.info(f"No farming tips available in the '{selected_category}' category yet.")
        
        with tip_tab2:
            st.write("Share your agricultural knowledge with the community")
            
            with st.form(key="tip_form"):
                tip_col1, tip_col2 = st.columns(2)
                
                with tip_col1:
                    tip_title = st.text_input("Title")
                    tip_category = st.selectbox(
                        "Category", 
                        ["Soil Management", "Water Management", "Pest Control", 
                         "Crop Selection", "Harvesting", "Equipment", "Weather", "Sustainable Practices"]
                    )
                
                with tip_col2:
                    tip_content = st.text_area("Content", height=150)
                
                submit_tip = st.form_submit_button("Share Tip")
                
                if submit_tip and tip_title and tip_content:
                    add_farming_tip(
                        user_id=st.session_state.current_user,
                        user_name=user['name'],
                        user_type=st.session_state.current_user_type,
                        title=tip_title,
                        content=tip_content,
                        category=tip_category
                    )
                    st.success(f"Your farming tip '{tip_title}' has been shared successfully!")
                    st.rerun()

# Add a footer
st.divider()
st.write("Connecting Farmers and Vendors-Sakshi Nimbalkar")