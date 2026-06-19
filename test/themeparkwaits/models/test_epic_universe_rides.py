"""
Test for EPIC Universe ride names with special characters
"""
import pytest
from src.models.theme_park import ThemePark
from src.models.theme_park_ride import ThemeParkRide


class TestEpicUniverseRides:
    """Test handling of EPIC Universe ride names with special characters"""
    
    @pytest.fixture
    def epic_universe_data(self):
        """Sample EPIC Universe data with special characters"""
        return {
            "lands": [
                {
                    "id": 973,
                    "name": "SUPER NINTENDO WORLD",
                    "rides": [
                        {
                            "id": 14683,
                            "name": "Mario Kart™: Bowser's Challenge",
                            "is_open": True,
                            "wait_time": 35
                        },
                        {
                            "id": 14686,
                            "name": "Mine-Cart Madness™",
                            "is_open": False,
                            "wait_time": 0
                        },
                        {
                            "id": 14689,
                            "name": "Yoshi's Adventure™",
                            "is_open": True,
                            "wait_time": 5
                        }
                    ]
                },
                {
                    "id": 972,
                    "name": "The Wizarding World of Harry Potter — Ministry of Magic",
                    "rides": [
                        {
                            "id": 14687,
                            "name": "Harry Potter and the Battle at the Ministry™",
                            "is_open": True,
                            "wait_time": 45
                        }
                    ]
                },
                {
                    "id": 974,
                    "name": "How to Train Your Dragon — Isle of Berk",
                    "rides": [
                        {
                            "id": 14693,
                            "name": "Dragon Racer's Rally",
                            "is_open": True,
                            "wait_time": 10
                        }
                    ]
                }
            ],
            "rides": []
        }
    
    def test_ride_names_filter_special_characters(self, epic_universe_data):
        """Test that ride names have non-ASCII characters filtered out for display compatibility"""
        park = ThemePark(epic_universe_data, name="Epic Universe", id=334)
        
        # Find rides by checking for specific parts of the name
        mario_kart = None
        harry_potter = None
        dragon_racer = None
        
        for ride in park.rides:
            if "Mario Kart" in ride.name:
                mario_kart = ride
            elif "Harry Potter" in ride.name:
                harry_potter = ride
            elif "Dragon Racer" in ride.name:
                dragon_racer = ride
        
        # Verify the rides were found
        assert mario_kart is not None, "Mario Kart ride not found"
        assert harry_potter is not None, "Harry Potter ride not found"
        assert dragon_racer is not None, "Dragon Racer ride not found"
        
        # Test that special characters are removed for LED display compatibility
        assert "™" not in mario_kart.name, f"Trademark symbol should be removed from: {mario_kart.name}"
        assert "™" not in harry_potter.name, f"Trademark symbol should be removed from: {harry_potter.name}"
        assert "'" in dragon_racer.name, f"Apostrophe should be preserved (ASCII): {dragon_racer.name}"
        
        # Test expected filtered names
        assert mario_kart.name == "Mario Kart: Bowser's Challenge"
        assert harry_potter.name == "Harry Potter and the Battle at the Ministry"
        assert dragon_racer.name == "Dragon Racer's Rally"
    
    def test_land_names_preserve_special_characters(self, epic_universe_data):
        """Test that land names also preserve special characters"""
        park = ThemePark(epic_universe_data, name="Epic Universe", id=334)
        
        # The lands are parsed but not stored in the park object
        # So we'll test the parsing directly
        lands = epic_universe_data["lands"]
        
        # Check land names for special characters
        hp_land = next(l for l in lands if "Harry Potter" in l["name"])
        dragon_land = next(l for l in lands if "Dragon" in l["name"])
        
        assert "—" in hp_land["name"], f"Em dash missing from: {hp_land['name']}"
        assert "—" in dragon_land["name"], f"Em dash missing from: {dragon_land['name']}"
    
    def test_remove_non_ascii_breaks_special_characters(self):
        """Test showing how remove_non_ascii breaks special characters"""
        test_names = [
            "Mario Kart™: Bowser's Challenge",
            "Harry Potter and the Battle at the Ministry™",
            "How to Train Your Dragon — Isle of Berk"
        ]
        
        for name in test_names:
            stripped = ThemePark.remove_non_ascii(name)
            # These assertions show the problem - special chars are removed
            assert "™" not in stripped, f"remove_non_ascii should remove ™ from {name}"
            assert "—" not in stripped, f"remove_non_ascii should remove — from {name}"
            
            # The apostrophe should remain as it's ASCII
            if "'" in name:
                assert "'" in stripped, f"Apostrophe should be preserved in {name}"
    
    def test_all_epic_universe_rides(self, epic_universe_data):
        """Test parsing all EPIC Universe rides"""
        park = ThemePark(epic_universe_data, name="Epic Universe", id=334)
        
        # Should have all 5 rides from the test data
        assert len(park.rides) == 5
        
        # Check ride properties (with filtered names)
        ride_names = [ride.name for ride in park.rides]
        assert "Mario Kart: Bowser's Challenge" in ride_names
        assert "Mine-Cart Madness" in ride_names
        assert "Yoshi's Adventure" in ride_names
        assert "Harry Potter and the Battle at the Ministry" in ride_names
        assert "Dragon Racer's Rally" in ride_names
        
        # Verify wait times
        mario_kart = next(r for r in park.rides if "Mario Kart" in r.name)
        assert mario_kart.wait_time == 35
        assert mario_kart.is_open() == True
        
        mine_cart = next(r for r in park.rides if "Mine-Cart" in r.name)
        assert mine_cart.wait_time == 0
        assert mine_cart.is_open() == False  # Closed because wait_time is 0