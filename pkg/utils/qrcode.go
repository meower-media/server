package utils

import (
	"fmt"
	"log"

	"github.com/skip2/go-qrcode"
)

// thanks ChatGPT
func GenerateSVGQRCode(content string) string {
	// Generate QR code matrix
	qr, err := qrcode.New(content, qrcode.Medium)
	if err != nil {
		log.Fatal(err)
	}

	// Get the QR code's bitmap (2D array)
	bitmap := qr.Bitmap()

	// Set block size to 1mm
	blockSize := 1 // 1mm per block

	// Define total size in mm (45mm x 45mm)
	totalSize := 45

	// Calculate the size of the QR code in mm
	qrSize := len(bitmap) * blockSize

	// Calculate the margin to center the QR code within the 45mm x 45mm space
	margin := (totalSize - qrSize) / 2

	// Start building SVG content
	svg := fmt.Sprintf(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %[1]d %[1]d" width="%[1]dmm" height="%[1]dmm">`, totalSize)

	// Iterate over the bitmap to create SVG rectangles for each black square
	for y := range bitmap {
		for x := range bitmap[y] {
			if bitmap[y][x] {
				// Draw black (filled) squares using currentColor, with offset for the margin
				svg += fmt.Sprintf(`<rect x="%d" y="%d" width="%d" height="%d" fill="currentColor"/>`,
					x*blockSize+margin, y*blockSize+margin, blockSize, blockSize)
			}
		}
	}

	svg += `</svg>`
	return svg
}
