import { getServerSession } from 'next-auth/next'
import { authOptions } from './auth/[...nextauth]'
import prisma from '../../lib/prisma'
import { getFlightPrice } from '../../lib/flights'

export default async function handler(req, res) {
  const session = await getServerSession(req, res, authOptions)

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const userId = session.user.id

  // GET - List user's alerts
  if (req.method === 'GET') {
    const alerts = await prisma.alert.findMany({
      where: { userId, isActive: true },
      orderBy: { createdAt: 'desc' },
    })
    return res.status(200).json(alerts)
  }

  // POST - Create new alert
  if (req.method === 'POST') {
    const { origin, destination, departureDate, maxPrice } = req.body

    if (!origin || !destination || !departureDate) {
      return res.status(400).json({ error: 'Missing required fields' })
    }

    // Fetch current price
    const currentPrice = await getFlightPrice(origin, destination, departureDate)

    const alert = await prisma.alert.create({
      data: {
        userId,
        origin: origin.toUpperCase(),
        destination: destination.toUpperCase(),
        departureDate: new Date(departureDate),
        maxPrice: maxPrice ? parseFloat(maxPrice) : null,
        lastPrice: currentPrice,
      },
    })

    // Save price history if we got a price
    if (currentPrice) {
      await prisma.priceHistory.create({
        data: {
          alertId: alert.id,
          price: currentPrice,
        },
      })
    }

    return res.status(201).json({ ...alert, currentPrice })
  }

  // DELETE - Remove alert
  if (req.method === 'DELETE') {
    const { id } = req.body

    await prisma.alert.updateMany({
      where: { id, userId },
      data: { isActive: false },
    })

    return res.status(200).json({ success: true })
  }

  return res.status(405).json({ error: 'Method not allowed' })
}
