'use client'
import "./globals.css"
import ThemeRegistry from "./ThemeRegistry/ThemeRegistry"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pl">
      <body>
        <ThemeRegistry>{children}</ThemeRegistry>
      </body>
    </html>
  )
}