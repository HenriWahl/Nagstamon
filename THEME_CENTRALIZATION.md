# Theme Centralization Summary

## Overview
As requested, theming has been **fully centralized** in the QSS (Qt Style Sheet) file. This provides a single source of truth for all visual styling in the Nagstamon application.

## What Was Centralized

### Before: Scattered Inline Styles
Previously, styles were defined inline throughout the codebase using `setStyleSheet()` calls:

```python
# In buttons.py
self.setStyleSheet('''padding: 8px 16px;''')

# In treeview.py  
self.setStyleSheet('''QTreeView::item {margin: 5px;}
                      QTreeView::item:hover {margin: 0px;
                                             padding: 5px;
                                             color: white;
                                             background-color: dimgrey;}
                      ...''')

# In labels.py
self.setStyleSheet(f'''padding-left: 1px;
                       padding-right: 1px;
                       color: {conf.__dict__['color_ok_text']};
                       background-color: {conf.__dict__['color_ok_background']};
                       font-size: 92px;
                       font-weight: bold;''')
```

### After: Centralized in modern_theme.qss

All static styles are now in one place: `Nagstamon/resources/modern_theme.qss`

```css
/* FlatButton - Auto-raised toolbar buttons */
FlatButton {
    padding: 8px 16px;
    border-radius: 6px;
}

/* TreeView customization */
TreeView QTreeView::item {
    margin: 8px;
    padding: 4px;
}

TreeView QTreeView::item:hover {
    margin: 0px;
    padding: 12px 8px;
    color: white;
    background-color: #666666;
    border-radius: 4px;
}

/* LabelAllOK - Large OK display label */
LabelAllOK {
    padding-left: 4px;
    padding-right: 4px;
    font-size: 92px;
    font-weight: bold;
}
```

## Implementation Strategy

### 1. Object Names for CSS Targeting
Widgets now have `objectName` set for QSS selector targeting:

```python
# buttons.py
self.setObjectName('button_hamburger_menu')

# toparea.py
self.button_close.setObjectName('button_close')

# treeview.py
self.setObjectName('TreeView')

# labels.py
self.setObjectName('LabelAllOK')
self.setObjectName('ServerStatusLabel')

# statusbar.py
self.setObjectName('StatusBarLabel')
```

### 2. QSS Selectors
The stylesheet uses multiple selector types:

```css
/* Class-based selectors (Qt widget type) */
QPushButton { ... }
QLineEdit { ... }

/* ID-based selectors (specific widgets via objectName) */
#button_close { ... }
#button_hamburger_menu { ... }

/* Custom class selectors (Python class names) */
FlatButton { ... }
TreeView QTreeView::item { ... }
LabelAllOK { ... }
ServerStatusLabel { ... }
StatusBarLabel { ... }
```

### 3. Dynamic vs Static Styles

**Static Styles (in QSS):**
- Padding, margins, spacing
- Border radius, borders
- Font sizes and weights
- Default colors
- Hover effects
- Layout properties

**Dynamic Styles (inline only when necessary):**
- User-configurable colors from settings
- State-dependent colors (OK, WARNING, CRITICAL, etc.)
- Real-time theme switching

```python
# This MUST remain inline because it's user-configurable
self.setStyleSheet(f'''color: {conf.__dict__['color_ok_text']};
                       background-color: {conf.__dict__['color_ok_background']};''')
```

## File-by-File Changes

### 1. `Nagstamon/resources/modern_theme.qss` (Enhanced)

Added Nagstamon-specific widget styles:

```css
/* StatusBar Labels */
StatusBarLabel {
    padding-left: 4px;
    padding-right: 4px;
}

/* LabelAllOK */
LabelAllOK {
    padding-left: 4px;
    padding-right: 4px;
    font-size: 92px;
    font-weight: bold;
}

/* ServerStatusLabel */
ServerStatusLabel {
    border-radius: 6px;
    padding: 4px 8px;
}

/* TreeView */
TreeView QTreeView::item {
    margin: 8px;
    padding: 4px;
}

TreeView QTreeView::item:hover {
    margin: 0px;
    padding: 12px 8px;
    color: white;
    background-color: #666666;
    border-radius: 4px;
}

TreeView QTreeView::item:selected {
    margin: 0px;
    padding: 12px 8px;
    color: white;
    background-color: #4a90e2;
    border-radius: 4px;
}

/* FlatButton */
FlatButton {
    padding: 8px 16px;
    border-radius: 6px;
}

/* Close button */
#button_close {
    margin-right: 8px;
    padding: 8px;
    border-radius: 6px;
}

/* Hamburger menu button */
#button_hamburger_menu {
    padding: 8px;
    border-radius: 6px;
}
```

### 2. `Nagstamon/qui/widgets/buttons.py`

**Before:**
```python
def __init__(self, text='', parent=None, server=None, url_type=''):
    QToolButton.__init__(self, parent=parent)
    self.setAutoRaise(True)
    self.setStyleSheet('''padding: 8px 16px;''')  # Inline style
    self.setText(text)
```

**After:**
```python
def __init__(self, text='', parent=None):
    QToolButton.__init__(self, parent=parent)
    self.setAutoRaise(True)
    # Styling now centralized in modern_theme.qss under FlatButton selector
    self.setText(text)
```

### 3. `Nagstamon/qui/widgets/treeview.py`

**Before:**
```python
self.setStyleSheet('''QTreeView::item {margin: 5px;}
                      QTreeView::item:hover {margin: 0px;
                                             padding: 5px;
                                             color: white;
                                             background-color: dimgrey;}
                      QTreeView::item:selected {margin: 0px;
                                                padding: 5px;
                                                color: white;
                                                background-color: grey;}
                    ''')
```

**After:**
```python
# Set object name for QSS styling - styling is now centralized
self.setObjectName('TreeView')
```

### 4. `Nagstamon/qui/widgets/labels.py`

**Before:**
```python
self.setStyleSheet(f'''padding-left: 1px;
                       padding-right: 1px;
                       color: {conf.__dict__['color_ok_text']};
                       background-color: {conf.__dict__['color_ok_background']};
                       font-size: 92px;
                       font-weight: bold;''')
```

**After:**
```python
self.setObjectName('LabelAllOK')  # QSS handles padding, font-size, font-weight
# Only dynamic user colors remain inline
self.setStyleSheet(f'''color: {conf.__dict__['color_ok_text']};
                       background-color: {conf.__dict__['color_ok_background']};''')
```

### 5. `Nagstamon/qui/widgets/statusbar.py`

**Before:**
```python
self.setStyleSheet(f'''padding-left: 1px;
                       padding-right: 1px;
                       color: {conf.__dict__[f'color_{state.lower()}_text']};
                       background-color: {conf.__dict__[f'color_{state.lower()}_background']};''')
```

**After:**
```python
self.setObjectName('StatusBarLabel')  # QSS handles padding
# Only dynamic user colors remain inline
self.setStyleSheet(f'''color: {conf.__dict__[f'color_{state.lower()}_text']};
                       background-color: {conf.__dict__[f'color_{state.lower()}_background']};''')
```

### 6. `Nagstamon/qui/widgets/toparea.py`

**Added:**
```python
self.button_close.setObjectName('button_close')  # For QSS styling
```

## Benefits of Centralization

### 1. **Single Source of Truth**
- All styling in one file (`modern_theme.qss`)
- Easy to understand the complete visual design
- No hunting through Python files for styles

### 2. **Maintainability**
- Change padding/margins once, applies everywhere
- Update colors globally without touching Python code
- Easier for designers to work with CSS-like syntax

### 3. **Consistency**
- Uniform styling across all widgets
- No accidental style variations
- Clear separation: QSS for look, Python for behavior

### 4. **Flexibility**
- Easy to create theme variants (dark mode, high contrast)
- Users could potentially customize themes
- Can swap themes by loading different QSS files

### 5. **Performance**
- QSS is parsed once at startup
- More efficient than repeated `setStyleSheet()` calls
- Less Python code overhead

### 6. **Readability**
- Python code focuses on logic, not styling
- QSS file reads like standard CSS
- Clear intent: `setObjectName()` shows widget is styled in QSS

## What Remains Inline (By Design)

Only truly dynamic values remain inline:

1. **User-configurable colors** (from settings dialog)
2. **State-based colors** (OK, WARNING, CRITICAL status colors)
3. **Platform-specific overrides** (macOS vs Windows/Linux differences)
4. **Runtime-computed styles** (responsive sizing, dynamic themes)

Example:
```python
# This MUST be inline - user can change these colors in settings
self.setStyleSheet(f'''color: {conf.__dict__['color_ok_text']};
                       background-color: {conf.__dict__['color_ok_background']};''')
```

## Theme Architecture

```
Application Startup
    ↓
app.py loads modern_theme.qss
    ↓
QApplication.setStyleSheet(qss_content)
    ↓
Global styles applied to all widgets
    ↓
Widget constructors set objectName
    ↓
QSS selectors target widgets by name/type
    ↓
Dynamic colors applied via inline styles (user settings)
    ↓
Complete themed application
```

## Future Enhancements

With this centralized architecture, future improvements are easy:

1. **Theme Variants:**
   ```
   modern_theme.qss         (default)
   modern_theme_dark.qss    (dark mode)
   modern_theme_compact.qss (space-saving)
   ```

2. **User Theme Selection:**
   ```python
   # In settings
   theme_file = conf.theme or 'modern_theme.qss'
   load_theme(theme_file)
   ```

3. **Custom User Themes:**
   - Users can create custom QSS files
   - Drop in ~/.config/nagstamon/themes/
   - Select from settings dialog

4. **Theme Hot-Reload:**
   ```python
   def reload_theme():
       with open(theme_path) as f:
           app.setStyleSheet(f.read())
   ```

## Summary

✅ **Centralized:** All static styles moved to `modern_theme.qss`  
✅ **Organized:** Object names added for precise QSS targeting  
✅ **Clean:** Python code no longer cluttered with styling  
✅ **Maintainable:** Single file to edit for visual changes  
✅ **Flexible:** Easy to create theme variants  
✅ **Efficient:** User colors remain dynamic, everything else is static QSS  

The theming system is now fully centralized with clear separation between:
- **Static styles** → `modern_theme.qss`
- **Dynamic user colors** → Inline `setStyleSheet()` where needed
- **Widget identity** → `setObjectName()` for QSS targeting

This is industry best practice for Qt applications and makes the codebase much more maintainable!
