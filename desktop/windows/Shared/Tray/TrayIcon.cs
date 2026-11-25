using Shared.Overlay;
using Drawing = System.Drawing;
using Forms = System.Windows.Forms;

namespace Shared.Tray;

/// <summary>
/// A system-tray icon with a dark context menu (WinForms <c>NotifyIcon</c>, pumped by the WPF dispatcher).
/// Build the menu with <see cref="Add"/>, <see cref="AddCheck"/>, <see cref="AddSubmenu"/> and <see cref="AddSeparator"/>;
/// <see cref="Opening"/> fires just before the menu shows so items can be refreshed.
/// </summary>
public sealed class TrayIcon : IDisposable
{
    private readonly Forms.NotifyIcon _icon;
    private readonly Forms.ContextMenuStrip _menu;
    private Drawing.Icon? _drawnIcon;

    public TrayIcon(string tooltip, Drawing.Icon icon)
    {
        _menu = new Forms.ContextMenuStrip
        {
            Renderer = new DarkMenuRenderer(),
            ShowImageMargin = false,
            ShowCheckMargin = true,
            Font = new Drawing.Font("Segoe UI", 9.5f),
            Padding = new Forms.Padding(2, 4, 2, 4),
        };
        _menu.Opening += (_, _) => Opening?.Invoke(this, EventArgs.Empty);

        _drawnIcon = icon;
        _icon = new Forms.NotifyIcon
        {
            Icon = icon,
            Text = tooltip.Length > 63 ? tooltip[..63] : tooltip,
            ContextMenuStrip = _menu,
            Visible = true,
        };
        _icon.MouseClick += (_, e) =>
        {
            if (e.Button == Forms.MouseButtons.Left) LeftClick?.Invoke(this, EventArgs.Empty);
        };
    }

    public event EventHandler? Opening;
    public event EventHandler? LeftClick;

    public Forms.ToolStripItemCollection Items => _menu.Items;

    public string Tooltip
    {
        set => _icon.Text = value.Length > 63 ? value[..63] : value;
    }

    public void SetIcon(Drawing.Icon icon)
    {
        var old = _drawnIcon;
        _drawnIcon = icon;
        _icon.Icon = icon;
        old?.Dispose();
    }

    public Forms.ToolStripMenuItem Add(string text, Action onClick, Forms.ToolStripItemCollection? into = null)
    {
        var item = new Forms.ToolStripMenuItem(text);
        item.Click += (_, _) => onClick();
        (into ?? Items).Add(item);
        return item;
    }

    public Forms.ToolStripMenuItem AddCheck(string text, Func<bool> isChecked, Action onClick, Forms.ToolStripItemCollection? into = null)
    {
        var item = new Forms.ToolStripMenuItem(text) { Checked = isChecked() };
        item.Click += (_, _) => onClick();
        Opening += (_, _) => item.Checked = isChecked();
        (into ?? Items).Add(item);
        return item;
    }

    public Forms.ToolStripMenuItem AddSubmenu(string text)
    {
        var item = new Forms.ToolStripMenuItem(text);
        if (item.DropDown is Forms.ToolStripDropDownMenu dd)
        {
            dd.Renderer = new DarkMenuRenderer();
            dd.ShowImageMargin = false;
            dd.ShowCheckMargin = true;
            dd.Font = _menu.Font;
        }
        Items.Add(item);
        return item;
    }

    public void AddSeparator(Forms.ToolStripItemCollection? into = null) => (into ?? Items).Add(new Forms.ToolStripSeparator());

    public Forms.ToolStripLabel AddLabel(string text)
    {
        var label = new Forms.ToolStripLabel(text) { ForeColor = DarkMenuRenderer.Subtle, Margin = new Forms.Padding(8, 2, 8, 2) };
        Items.Add(label);
        return label;
    }

    public void Dispose()
    {
        _icon.Visible = false;
        _icon.Dispose();
        _menu.Dispose();
        _drawnIcon?.Dispose();
    }
}

/// <summary>A dark, rounded-feeling renderer for the tray menu, highlighted with the accent colour.</summary>
internal sealed class DarkMenuRenderer : Forms.ToolStripProfessionalRenderer
{
    public static readonly Drawing.Color Back = Drawing.Color.FromArgb(0x2B, 0x2B, 0x30);
    public static readonly Drawing.Color Border = Drawing.Color.FromArgb(0x44, 0x44, 0x4A);
    public static readonly Drawing.Color Text = Drawing.Color.FromArgb(0xF2, 0xF2, 0xF7);
    public static readonly Drawing.Color Subtle = Drawing.Color.FromArgb(0x9A, 0x9A, 0xA3);

    public DarkMenuRenderer() : base(new DarkColors()) => RoundedEdges = true;

    private static Drawing.Color AccentColor
    {
        get
        {
            var c = Ui.Accent.Current;
            return Drawing.Color.FromArgb(c.R, c.G, c.B);
        }
    }

    protected override void OnRenderItemText(Forms.ToolStripItemTextRenderEventArgs e)
    {
        e.TextColor = e.Item.Enabled ? Text : Subtle;
        base.OnRenderItemText(e);
    }

    protected override void OnRenderArrow(Forms.ToolStripArrowRenderEventArgs e)
    {
        e.ArrowColor = Text;
        base.OnRenderArrow(e);
    }

    protected override void OnRenderMenuItemBackground(Forms.ToolStripItemRenderEventArgs e)
    {
        if (!e.Item.Selected || !e.Item.Enabled)
        {
            base.OnRenderMenuItemBackground(e);
            return;
        }
        var g = e.Graphics;
        g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias;
        var r = new Drawing.Rectangle(4, 1, e.Item.Width - 8, e.Item.Height - 2);
        using var path = RoundedRect(r, 5);
        var a = AccentColor;
        using var brush = new Drawing.SolidBrush(Drawing.Color.FromArgb(0x55, a.R, a.G, a.B));
        g.FillPath(brush, path);
    }

    protected override void OnRenderItemCheck(Forms.ToolStripItemImageRenderEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias;
        var r = e.ImageRectangle;
        var cx = r.X + r.Width / 2f;
        var cy = r.Y + r.Height / 2f;
        using var pen = new Drawing.Pen(AccentColor, 2f) { StartCap = Drawing.Drawing2D.LineCap.Round, EndCap = Drawing.Drawing2D.LineCap.Round };
        g.DrawLines(pen, new[]
        {
            new Drawing.PointF(cx - 5, cy),
            new Drawing.PointF(cx - 1.5f, cy + 3.5f),
            new Drawing.PointF(cx + 5, cy - 4),
        });
    }

    protected override void OnRenderSeparator(Forms.ToolStripSeparatorRenderEventArgs e)
    {
        var y = e.Item.Height / 2;
        using var pen = new Drawing.Pen(Border);
        e.Graphics.DrawLine(pen, 10, y, e.Item.Width - 10, y);
    }

    internal static Drawing.Drawing2D.GraphicsPath RoundedRect(Drawing.Rectangle r, int radius)
    {
        var path = new Drawing.Drawing2D.GraphicsPath();
        var d = radius * 2;
        path.AddArc(r.X, r.Y, d, d, 180, 90);
        path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    private sealed class DarkColors : Forms.ProfessionalColorTable
    {
        public override Drawing.Color ToolStripDropDownBackground => Back;
        public override Drawing.Color MenuBorder => Border;
        public override Drawing.Color MenuItemBorder => Drawing.Color.Transparent;
        public override Drawing.Color MenuItemSelected => Drawing.Color.FromArgb(0x3A, 0x3A, 0x40);
        public override Drawing.Color ImageMarginGradientBegin => Back;
        public override Drawing.Color ImageMarginGradientMiddle => Back;
        public override Drawing.Color ImageMarginGradientEnd => Back;
        public override Drawing.Color CheckBackground => Back;
        public override Drawing.Color CheckSelectedBackground => Back;
        public override Drawing.Color CheckPressedBackground => Back;
        public override Drawing.Color SeparatorDark => Border;
        public override Drawing.Color SeparatorLight => Back;
    }
}

/// <summary>Draws tray icons in code, so no .ico asset is needed.</summary>
public static class TrayIconArt
{
    /// <summary>Renders <paramref name="draw"/> onto a transparent square and converts it to an icon.</summary>
    public static Drawing.Icon Draw(Action<Drawing.Graphics, int> draw, int size = 32)
    {
        using var bmp = new Drawing.Bitmap(size, size, Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (var g = Drawing.Graphics.FromImage(bmp))
        {
            g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias;
            g.PixelOffsetMode = Drawing.Drawing2D.PixelOffsetMode.HighQuality;
            g.Clear(Drawing.Color.Transparent);
            draw(g, size);
        }
        var hIcon = bmp.GetHicon();
        try
        {
            using var temp = Drawing.Icon.FromHandle(hIcon);
            return (Drawing.Icon)temp.Clone(); // the clone owns its own handle
        }
        finally
        {
            Native.DestroyIcon(hIcon);
        }
    }

    /// <summary>The icon size the tray wants at the current DPI.</summary>
    public static int PreferredSize => Forms.SystemInformation.SmallIconSize.Width <= 16 ? 32 : Math.Min(64, Forms.SystemInformation.SmallIconSize.Width * 2);

    public static Drawing.Color FromWpf(System.Windows.Media.Color c) => Drawing.Color.FromArgb(c.A, c.R, c.G, c.B);
}
