Add-Type -AssemblyName System.Drawing

$sourceImage = Join-Path $PSScriptRoot 'ad9b84ac-a093-4e2c-aa56-fdeb0e63ff57.jpg'
$manifestPath = Join-Path $PSScriptRoot 'elements_manifest.json'

$specs = @(
    [pscustomobject]@{
        id = 'jiutan'
        label = '玲珑酒坛'
        file = 'tile_01_jiutan.png'
        rect = @{ x = 20; y = 15; w = 205; h = 215 }
    },
    [pscustomobject]@{
        id = 'peach_letter'
        label = '桃花笺'
        file = 'tile_02_peach_letter.png'
        rect = @{ x = 260; y = 35; w = 240; h = 205 }
    },
    [pscustomobject]@{
        id = 'bamboo_flute'
        label = '青竹笛'
        file = 'tile_03_bamboo_flute.png'
        rect = @{ x = 510; y = 15; w = 240; h = 225 }
    },
    [pscustomobject]@{
        id = 'fox_mask'
        label = '赤狐面具'
        file = 'tile_04_fox_mask.png'
        rect = @{ x = 760; y = 15; w = 220; h = 215 }
    },
    [pscustomobject]@{
        id = 'gold_ingot'
        label = '小金元宝'
        file = 'tile_05_gold_ingot.png'
        rect = @{ x = 270; y = 300; w = 240; h = 165 }
    },
    [pscustomobject]@{
        id = 'crane_feather'
        label = '白鹤羽翎'
        file = 'tile_06_crane_feather.png'
        rect = @{ x = 555; y = 300; w = 210; h = 175 }
    },
    [pscustomobject]@{
        id = 'purple_spider'
        label = '紫色毒蛛'
        file = 'tile_07_purple_spider.png'
        rect = @{ x = 790; y = 305; w = 190; h = 155 }
    }
)

function Get-BackgroundColor {
    param([System.Drawing.Bitmap]$Bitmap)

    $samples = @(
        $Bitmap.GetPixel(0, 0),
        $Bitmap.GetPixel($Bitmap.Width - 1, 0),
        $Bitmap.GetPixel(0, $Bitmap.Height - 1),
        $Bitmap.GetPixel($Bitmap.Width - 1, $Bitmap.Height - 1)
    )

    $r = [Math]::Min(255, [int](($samples | Measure-Object -Property R -Average).Average + 0.5))
    $g = [Math]::Min(255, [int](($samples | Measure-Object -Property G -Average).Average + 0.5))
    $b = [Math]::Min(255, [int](($samples | Measure-Object -Property B -Average).Average + 0.5))
    return [System.Drawing.Color]::FromArgb(255, $r, $g, $b)
}

function Test-IsNearBackground {
    param(
        [System.Drawing.Color]$Color,
        [System.Drawing.Color]$Background,
        [int]$ThresholdSquared
    )

    $dr = [int]$Color.R - [int]$Background.R
    $dg = [int]$Color.G - [int]$Background.G
    $db = [int]$Color.B - [int]$Background.B
    return (($dr * $dr) + ($dg * $dg) + ($db * $db)) -le $ThresholdSquared
}

function Get-BackgroundMask {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Color]$Background,
        [int]$Threshold = 26
    )

    $thresholdSquared = $Threshold * $Threshold
    $width = $Bitmap.Width
    $height = $Bitmap.Height
    $candidate = [bool[,]]::new($width, $height)
    $mask = [bool[,]]::new($width, $height)
    $queued = [bool[,]]::new($width, $height)
    $queue = [System.Collections.Generic.Queue[System.Drawing.Point]]::new()

    for ($y = 0; $y -lt $height; $y++) {
        for ($x = 0; $x -lt $width; $x++) {
            $pixel = $Bitmap.GetPixel($x, $y)
            $candidate.SetValue(
                (Test-IsNearBackground -Color $pixel -Background $Background -ThresholdSquared $thresholdSquared),
                $x,
                $y
            )
        }
    }

    for ($x = 0; $x -lt $width; $x++) {
        $bottomY = $height - 1
        if ($candidate.GetValue($x, 0) -and (-not $queued.GetValue($x, 0))) {
            $queued.SetValue($true, $x, 0)
            $queue.Enqueue([System.Drawing.Point]::new($x, 0))
        }
        if ($candidate.GetValue($x, $bottomY) -and (-not $queued.GetValue($x, $bottomY))) {
            $queued.SetValue($true, $x, $bottomY)
            $queue.Enqueue([System.Drawing.Point]::new($x, $bottomY))
        }
    }
    for ($y = 0; $y -lt $height; $y++) {
        $rightX = $width - 1
        if ($candidate.GetValue(0, $y) -and (-not $queued.GetValue(0, $y))) {
            $queued.SetValue($true, 0, $y)
            $queue.Enqueue([System.Drawing.Point]::new(0, $y))
        }
        if ($candidate.GetValue($rightX, $y) -and (-not $queued.GetValue($rightX, $y))) {
            $queued.SetValue($true, $rightX, $y)
            $queue.Enqueue([System.Drawing.Point]::new($rightX, $y))
        }
    }

    $offsets = @(
        [System.Drawing.Point]::new(-1, 0),
        [System.Drawing.Point]::new(1, 0),
        [System.Drawing.Point]::new(0, -1),
        [System.Drawing.Point]::new(0, 1),
        [System.Drawing.Point]::new(-1, -1),
        [System.Drawing.Point]::new(1, -1),
        [System.Drawing.Point]::new(-1, 1),
        [System.Drawing.Point]::new(1, 1)
    )

    while ($queue.Count -gt 0) {
        $point = $queue.Dequeue()
        if ($mask.GetValue($point.X, $point.Y)) {
            continue
        }

        $mask.SetValue($true, $point.X, $point.Y)
        foreach ($offset in $offsets) {
            $nx = $point.X + $offset.X
            $ny = $point.Y + $offset.Y
            if ($nx -lt 0 -or $ny -lt 0 -or $nx -ge $width -or $ny -ge $height) {
                continue
            }
            if ($candidate.GetValue($nx, $ny) -and (-not $queued.GetValue($nx, $ny))) {
                $queued.SetValue($true, $nx, $ny)
                $queue.Enqueue([System.Drawing.Point]::new($nx, $ny))
            }
        }
    }

    Write-Output -NoEnumerate $mask
}

function Export-Cutout {
    param(
        [System.Drawing.Bitmap]$Source,
        [object]$Spec
    )

    $rect = [System.Drawing.Rectangle]::new($Spec.rect.x, $Spec.rect.y, $Spec.rect.w, $Spec.rect.h)
    $crop = $Source.Clone($rect, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

    try {
        $background = Get-BackgroundColor -Bitmap $crop
        $mask = Get-BackgroundMask -Bitmap $crop -Background $background

        $minX = $crop.Width
        $minY = $crop.Height
        $maxX = -1
        $maxY = -1

        for ($y = 0; $y -lt $crop.Height; $y++) {
            for ($x = 0; $x -lt $crop.Width; $x++) {
                if ($mask.GetValue($x, $y)) {
                    $pixel = $crop.GetPixel($x, $y)
                    $crop.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, $pixel.R, $pixel.G, $pixel.B))
                    continue
                }

                if ($x -lt $minX) { $minX = $x }
                if ($y -lt $minY) { $minY = $y }
                if ($x -gt $maxX) { $maxX = $x }
                if ($y -gt $maxY) { $maxY = $y }
            }
        }

        if ($maxX -lt 0 -or $maxY -lt 0) {
            throw "No foreground detected for $($Spec.id)."
        }

        $padding = 8
        $left = [Math]::Max(0, $minX - $padding)
        $top = [Math]::Max(0, $minY - $padding)
        $right = [Math]::Min($crop.Width - 1, $maxX + $padding)
        $bottom = [Math]::Min($crop.Height - 1, $maxY + $padding)
        $trimRect = [System.Drawing.Rectangle]::new($left, $top, $right - $left + 1, $bottom - $top + 1)
        $final = $crop.Clone($trimRect, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

        try {
            $outputPath = Join-Path $PSScriptRoot $Spec.file
            $final.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
            return [pscustomobject]@{
                id = $Spec.id
                label = $Spec.label
                file = $Spec.file
                width = $final.Width
                height = $final.Height
                source = [pscustomobject]@{
                    image = [System.IO.Path]::GetFileName($sourceImage)
                    rect = $Spec.rect
                }
            }
        }
        finally {
            $final.Dispose()
        }
    }
    finally {
        $crop.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $sourceImage)) {
    throw "Source image not found: $sourceImage"
}

$source = [System.Drawing.Bitmap]::new($sourceImage)
try {
    $manifest = foreach ($spec in $specs) {
        Export-Cutout -Source $source -Spec $spec
    }
}
finally {
    $source.Dispose()
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ForEach-Object { "{0}`t{1}`t{2}x{3}" -f $_.file, $_.label, $_.width, $_.height }
