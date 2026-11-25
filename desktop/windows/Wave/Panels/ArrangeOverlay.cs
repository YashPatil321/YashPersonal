using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shapes;
using Wave.Desktop;

namespace Wave.Panels;

/// <summary>
/// Drawn over a widget while arranging: drag anywhere to move, drag the corner grip to resize, Done to finish.
/// It is a separate layered window (WPF content cannot be drawn over the WebView2 HWND), owned by the widget, and the
/// widget follows its rectangle.
/// </summary>
internal sealed class ArrangeOverlay : Window
{
    private const double MinWidthDip = 240, MinHeightDip = 120;
    private readonly IntPtr _owner;
    private Win32.RECT _initial;
    private IntPtr _hwnd;

    public ArrangeOverlay(IntPtr owner, Win32.RECT initial, string title)
    {
        _owner = owner;
        _initial = initial;
        Title = "Arrange " + title;
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        ResizeMode = ResizeMode.NoResize;
        ShowInTaskbar = false;
        Topmost = true;
        WindowStartupLocation = WindowStartupLocation.Manual;
        FontFamily = new FontFamily("Segoe UI Variable Text, Segoe UI");

        var root = new Grid { Background = new SolidColorBrush(Color.FromArgb(0x40, 0, 0, 0)), Cursor = Cursors.SizeAll };
        root.Children.Add(new Rectangle
        {
            Stroke = new SolidColorBrush(Color.FromArgb(0xCC, 0xFF, 0xFF, 0xFF)),
            StrokeThickness = 2,
            StrokeDashArray = new DoubleCollection { 4, 3 },
            RadiusX = 14,
            RadiusY = 14,
            Margin = new Thickness(2),
            IsHitTestVisible = false,
        });

        var header = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(12, 10, 12, 0), VerticalAlignment = VerticalAlignment.Top };
        var done = new Button { Content = "Done", Padding = new Thickness(16, 5, 16, 5), IsDefault = true, Cursor = Cursors.Hand };
        done.SetResourceReference(StyleProperty, "AccentButton");
        done.Click += (_, _) => Done?.Invoke();
        header.Children.Add(done);
        header.Children.Add(new TextBlock
        {
            Text = "Drag to move · corner to resize · " + title,
            Foreground = Brushes.White,
            FontWeight = FontWeights.SemiBold,
            FontSize = 13,
            Margin = new Thickness(12, 0, 0, 0),
            VerticalAlignment = VerticalAlignment.Center,
            IsHitTestVisible = false,
        });
        root.Children.Add(header);

        var grip = new Thumb
        {
            Width = 30,
            Height = 30,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Bottom,
            Cursor = Cursors.SizeNWSE,
            Template = GripTemplate(),
        };
        grip.DragDelta += (_, e) =>
        {
            Width = Math.Max(MinWidthDip, ActualWidth + e.HorizontalChange);
            Height = Math.Max(MinHeightDip, ActualHeight + e.VerticalChange);
        };
        root.Children.Add(grip);

        root.MouseLeftButtonDown += (_, e) =>
        {
            if (e.OriginalSource is DependencyObject d && IsInside<Thumb>(d)) return;
            if (e.OriginalSource is DependencyObject b && IsInside<Button>(b)) return;
            try { DragMove(); }
            catch (InvalidOperationException) { }
        };
        Content = root;

        LocationChanged += (_, _) => Report();
        SizeChanged += (_, _) => Report();
        KeyDown += (_, e) =>
        {
            if (e.Key is Key.Escape or Key.Enter) Done?.Invoke();
        };
    }

    /// <summary>The overlay moved or resized; the widget should take this rectangle (screen pixels).</summary>
    public event Action<Win32.RECT>? Moved;

    public event Action? Done;

    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        _hwnd = new WindowInteropHelper(this).Handle;
        new WindowInteropHelper(this).Owner = _owner;
        Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, _initial.Left, _initial.Top, _initial.Width, _initial.Height, 0);
    }

    private void Report()
    {
        if (_hwnd == IntPtr.Zero || !IsLoaded) return;
        if (Win32.GetWindowRect(_hwnd, out var r) && r.Width > 0) Moved?.Invoke(r);
    }

    private static bool IsInside<T>(DependencyObject d) where T : DependencyObject
    {
        for (var cur = d; cur is not null; cur = VisualTreeHelper.GetParent(cur))
            if (cur is T) return true;
        return false;
    }

    private static ControlTemplate GripTemplate()
    {
        var t = new ControlTemplate(typeof(Thumb));
        var grid = new FrameworkElementFactory(typeof(Grid));
        grid.SetValue(Panel.BackgroundProperty, Brushes.Transparent);
        var path = new FrameworkElementFactory(typeof(Path));
        path.SetValue(Path.DataProperty, Geometry.Parse("M 26,8 L 8,26 M 26,15 L 15,26 M 26,22 L 22,26"));
        path.SetValue(Shape.StrokeProperty, Brushes.White);
        path.SetValue(Shape.StrokeThicknessProperty, 2.0);
        path.SetValue(Shape.StrokeStartLineCapProperty, PenLineCap.Round);
        path.SetValue(Shape.StrokeEndLineCapProperty, PenLineCap.Round);
        grid.AppendChild(path);
        t.VisualTree = grid;
        return t;
    }
}
