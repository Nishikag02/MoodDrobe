// Hands a set of images from one page to the Studio (e.g. selected pins on the pinboard).
let pending: File[] | null = null

export function handOffImages(files: File[]) {
  pending = files.slice(0, 8)
}

export function takeHandedOffImages(): File[] | null {
  const f = pending
  pending = null
  return f
}
