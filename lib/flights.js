export async function getFlightPrice(origin, destination, departureDate) {
  try {
    const params = new URLSearchParams({
      engine: 'google_flights',
      departure_id: origin.toUpperCase(),
      arrival_id: destination.toUpperCase(),
      outbound_date: departureDate,
      currency: 'USD',
      hl: 'en',
      type: '2', // One-way
      api_key: process.env.SERPAPI_KEY,
    })

    const response = await fetch(`https://serpapi.com/search?${params}`)
    const data = await response.json()

    if (data.error) {
      console.error('SerpApi error:', data.error)
      return null
    }

    const flights = data.best_flights || data.other_flights || []
    
    if (flights.length > 0 && flights[0].price) {
      return parseFloat(flights[0].price)
    }

    return null
  } catch (error) {
    console.error('Flight price fetch error:', error)
    return null
  }
}
