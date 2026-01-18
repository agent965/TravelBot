import { Resend } from 'resend'

const resend = new Resend(process.env.RESEND_API_KEY)

export async function sendPriceAlert({ to, origin, destination, date, price, oldPrice }) {
  const priceDrop = oldPrice ? (oldPrice - price).toFixed(2) : null

  try {
    await resend.emails.send({
      from: 'TrackRoth <alerts@trackroth.com>',
      to: to,
      subject: `✈️ Price Drop Alert: ${origin} → ${destination}`,
      html: `
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
          <h1 style="color: #0f172a;">✈️ Flight Price Alert!</h1>
          <div style="background: #f1f5f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="margin: 0 0 10px 0; color: #0f172a;">${origin} → ${destination}</h2>
            <p style="margin: 5px 0; color: #475569;">Date: ${date}</p>
            <p style="margin: 5px 0; font-size: 24px; font-weight: bold; color: #16a34a;">
              $${price.toFixed(2)}
            </p>
            ${priceDrop ? `<p style="margin: 5px 0; color: #16a34a;">📉 Down $${priceDrop} from last check!</p>` : ''}
          </div>
          <a href="https://www.google.com/travel/flights?q=${origin}%20to%20${destination}%20${date}" 
             style="display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
            Book Now on Google Flights
          </a>
          <p style="margin-top: 30px; color: #94a3b8; font-size: 12px;">
            You're receiving this because you set up a flight alert on TrackRoth.
          </p>
        </div>
      `,
    })
    return true
  } catch (error) {
    console.error('Email send error:', error)
    return false
  }
}
