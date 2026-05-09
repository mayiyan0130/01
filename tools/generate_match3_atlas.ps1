Add-Type -AssemblyName System.Drawing

$projectRoot = Split-Path $PSScriptRoot -Parent
$sourceDir = Join-Path $projectRoot 'picture\sanxiao'
$outputDir = Join-Path $projectRoot 'web\assets\sanxiao'
$atlasImagePath = Join-Path $outputDir 'chapter01_match3_atlas.png'
$atlasJsonPath = Join-Path $outputDir 'chapter01_match3_atlas.json'

$tiles = @(
    [pscustomobject]@{ code = '01'; id = 'jiutan'; label = '玲珑酒坛'; file = 'tile_01_jiutan.png' },
    [pscustomobject]@{ code = '02'; id = 'peach_letter'; label = '桃花笺'; file = 'tile_02_peach_letter.png' },
    [pscustomobject]@{ code = '04'; id = 'fox_mask'; label = '赤狐面具'; file = 'tile_04_fox_mask.png' },
    [pscustomobject]@{ code = '05'; id = 'gold_ingot'; label = '小金元宝'; file = 'tile_05_gold_ingot.png' }
)

$cellSize = 192
$padding = 12
$columns = 2
$rows = [int][Math]::Ceiling($tiles.Count / $columns)
$atlasWidth = $columns * $cellSize
$atlasHeight = $rows * $cellSize

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$bitmap = [System.Drawing.Bitmap]::new($atlasWidth, $atlasHeight, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$graphics.Clear([System.Drawing.Color]::Transparent)

$frames = [ordered]@{}
$tileOrder = @()

try {
    for ($index = 0; $index -lt $tiles.Count; $index++) {
        $tile = $tiles[$index]
        $tilePath = Join-Path $sourceDir $tile.file
        if (-not (Test-Path -LiteralPath $tilePath)) {
            throw "Missing source tile: $tilePath"
        }

        $column = $index % $columns
        $row = [int][Math]::Floor($index / $columns)
        $cellX = $column * $cellSize
        $cellY = $row * $cellSize

        $image = [System.Drawing.Image]::FromFile($tilePath)
        try {
            $maxWidth = $cellSize - ($padding * 2)
            $maxHeight = $cellSize - ($padding * 2)
            $scale = [Math]::Min($maxWidth / $image.Width, $maxHeight / $image.Height)
            $drawWidth = [int][Math]::Round($image.Width * $scale)
            $drawHeight = [int][Math]::Round($image.Height * $scale)
            $drawX = $cellX + [int][Math]::Floor(($cellSize - $drawWidth) / 2)
            $drawY = $cellY + [int][Math]::Floor(($cellSize - $drawHeight) / 2)

            $graphics.DrawImage($image, $drawX, $drawY, $drawWidth, $drawHeight)

            $frames[$tile.id] = [ordered]@{
                frame = [ordered]@{
                    x = $cellX
                    y = $cellY
                    w = $cellSize
                    h = $cellSize
                }
                spriteSourceSize = [ordered]@{
                    x = $drawX - $cellX
                    y = $drawY - $cellY
                    w = $drawWidth
                    h = $drawHeight
                }
                sourceSize = [ordered]@{
                    w = $cellSize
                    h = $cellSize
                }
                code = $tile.code
                id = $tile.id
                label = $tile.label
                index = $index
            }
            $tileOrder += $tile.id
        }
        finally {
            $image.Dispose()
        }
    }

    $bitmap.Save($atlasImagePath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

$atlas = [ordered]@{
    meta = [ordered]@{
        image = [System.IO.Path]::GetFileName($atlasImagePath)
        imagePath = '/static/assets/sanxiao/chapter01_match3_atlas.png'
        size = [ordered]@{
            w = $atlasWidth
            h = $atlasHeight
        }
        cell = [ordered]@{
            w = $cellSize
            h = $cellSize
        }
        padding = $padding
        chapter = 'chapter-01'
        miniGame = 'match3'
        elementCodes = @('01', '02', '04', '05')
    }
    tileOrder = $tileOrder
    frames = $frames
}

$atlas | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $atlasJsonPath -Encoding UTF8

Write-Output $atlasImagePath
Write-Output $atlasJsonPath
