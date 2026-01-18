import prisma from '../../../lib/prisma'
import { getFlightPrice } from '../../../lib/flights'
import { sendPriceAlert } from '../../../lib/email'

export default async function handler(req, res) {
  // Verify cron secret to prevent unauthorized calls
  if (req.headers.authorization !== `Bearer ${process.env.CRON_SECRET}`) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const alerts = await prisma.alert.findMany({
    where: {
      isActive: true,
      departureDate: { gte: new Date() },
    },
    include: { user: true },
  })

  let checked = 0
  let notified = 0

  for (const alert of alerts) {
    const price = await getFlightPrice(
      alert.origin,
      alert.destination,
      alert.departureDate.toISOString().split('T')[0]
    )

    if (!price) continue
    checked++

    // Save price history
    await prisma.priceHistory.create({
      data: {
        alertId: alert.id,
        price,
      },
    })

    let shouldNotify = false
    let reason = ''

    // Check if price hit target
    if (alert.maxPrice && price <= alert.maxPrice) {
      shouldNotify = true
      reason = 'Price hit your target!'
    }
    // Check if price dropped >5%
    else if (alert.lastPrice && price < alert.lastPrice * 0.95) {
      shouldNotify = true
      reason = 'Price dropped more than 5%!'
    }

    if (shouldNotify && alert.user.email) {
      await sendPriceAlert({
        to: alert.user.email,
        origin: alert.origin,
        destination: alert.destination,
        date: alert.departureDate.toISOString().split('T')[0],
        price,
        oldPrice: alert.lastPrice,
      })
      notified++
    }

    // Update last price
    await prisma.alert.update({
      where: { id: alert.id },
      data: { lastPrice: price },
    })
  }

  return res.status(200).json({
    success: true,
    alertsChecked: checked,
    notificationsSent: notified,
  })
}
