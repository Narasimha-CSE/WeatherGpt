
(() => {
    async function detectLocation() {
        const cityInput = document.getElementById("cityInput");
        const searchBtn = document.getElementById("searchBtn");
        const errorElement = document.getElementById("error");

        if (!navigator.geolocation) {
            errorElement.textContent =
                "Your browser does not support location detection.";
            return;
        }

        // Ask for permission when the home page opens.
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                try {
                    // Convert the detected coordinates into a city.
                    const response = await fetch(
                        "https://nominatim.openstreetmap.org/reverse" +
                        `?format=jsonv2&lat=${latitude}&lon=${longitude}`
                    );

                    if (!response.ok) {
                        throw new Error("Unable to identify your city.");
                    }

                    const data = await response.json();
                    const address = data.address || {};

                    const city =
                        address.city ||
                        address.town ||
                        address.village ||
                        address.municipality ||
                        address.county ||
                        address.state_district;

                    if (!city) {
                        throw new Error("Could not identify your city.");
                    }

                    // Fill your EXISTING city search box.
                    cityInput.value = city;

                    // Automatically run your EXISTING weather search.
                    searchBtn.click();

                    console.log(
                        "Location detected:",
                        city,
                        latitude,
                        longitude
                    );

                } catch (error) {
                    console.error("Location error:", error);

                    errorElement.textContent =
                        "Could not fetch your location. Please search for a city.";
                }
            },

            (error) => {
                console.warn("Location permission or detection error:", error);

                errorElement.textContent =
                    error.code === 1
                        ? "Location access denied. Please enter your city manually."
                        : "Unable to detect location. Please search for your city.";
            },

            {
                enableHighAccuracy: false,
                timeout: 15000,
                maximumAge: 300000
            }
        );
    }

    // Run automatically when the home page loads.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", detectLocation);
    } else {
        detectLocation();
    }
})();
