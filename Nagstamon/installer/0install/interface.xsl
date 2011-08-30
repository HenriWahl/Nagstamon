<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:zi="http://zero-install.sourceforge.net/2004/injector/interface"
		version="1.0">

  <xsl:output method="xml" encoding="utf-8"
	doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"/>

  <xsl:template match="/zi:interface">
    <html>
      <head>
        <title>
          <xsl:value-of select="zi:name"/>
        </title>
	<style type='text/css'>
	  html { background: #d0d0ff; }
	  body { background: #d0d0ff; margin: 0; padding: 0; color: black;}
	  h1 { text-align: center; border-bottom: 2px solid #d0d0ff; padding-bottom: .5em; }
	  div.main { padding: 1em; background: white;
	  	    -moz-border-radius: 1em 1em 1em 1em; max-width: 60em;
		    margin-left: auto; margin-right: auto;
		    margin-top: 1em; margin-bottom: 1em;}
	  dt { font-weight: bold; text-transform:capitalize; }
	  dd { padding-bottom: 1em; }
	  dl.group { margin: 0.5em; padding: 0.5em; border: 1px dashed #888;}
	  dl.impl { padding: 0.2em 1em 0.2em 1em; margin: 0.5em; border: 1px solid black; background: white;}
	  pre { background: #ddd; color: black; padding: 0.2cm; }
	  table { width: 100% }
	  th { background: #d0d0ff; text-align: left; }
	  td { background: #e0e0ff; text-align: left; }
	</style>
      </head>
      <body>
       <div class='main'>
        <h1><xsl:value-of select="zi:name"/> - <xsl:value-of select='zi:summary'/></h1>

	<dl>
	 <dt>Overview</dt>
	 <dd>
	<xsl:choose>
	 <xsl:when test='//zi:implementation[@main] | //zi:group[@main]'>
	  <p>This is a Zero Install feed. To run this program from the command-line, use this
	  command:</p>
	  <pre>$ 0launch <xsl:value-of select='/zi:interface/@uri'/></pre>
	  <p>
	  The <b>0alias</b> command can be used to create a short-cut to run it again later.
	  </p>
	  <p>
	  If you use a graphical desktop, you can drag <a href='{/zi:interface/@uri}'>the feed's URL</a> to
	  an installer such as <a href='http://rox.sourceforge.net/desktop/AddApp'>AddApp</a> (ROX),
	  <a href='http://rox.sourceforge.net/desktop/node/269'>the Xfce 4.4 panel</a>, or
	  <a href='http://rox.sourceforge.net/desktop/node/402'>Zero2Desktop</a> (GNOME and KDE).
	  </p>
	  <p>
	  If you don't have the <b>0launch</b> command, download it from
	  <a href='http://0install.net/injector.html'>the 0install.net web-site</a>, which also contains
	  documentation about how the Zero Install system works.</p>
	 </xsl:when>
	 <xsl:otherwise>
	  <p>This is a Zero Install feed.
	  This software cannot be run as an application directly. It is a library for other programs to use.</p>
	  <p>For more information about Zero Install, see <a href='http://0install.net'>0install.net</a>.</p>
	 </xsl:otherwise>
	</xsl:choose>
	</dd>

	  <xsl:apply-templates mode='dl' select='*|@*'/>

	<dt>Available versions</dt>
	<dd>
	  <xsl:choose>
	    <xsl:when test='//zi:implementation'>
	      <p>The list below is just for information; Zero Install will automatically download one of
	      these versions for you.
	      </p>
	      <table>
	       <tr><th>Version</th><th>Released</th><th>Stability</th><th>Platform</th><th>Download</th></tr>
	       <xsl:for-each select='//zi:implementation'>
	        <tr>
		 <td><xsl:value-of select='(ancestor-or-self::*[@version])[last()]/@version'/>
		   <xsl:if test='(ancestor-or-self::*[@version])[last()]/@version-modifier'><xsl:value-of select='(ancestor-or-self::*[@version])[last()]/@version-modifier'/></xsl:if>
		 </td>
	         <td><xsl:value-of select='(ancestor-or-self::*[@released])[last()]/@released'/></td>
	         <td><xsl:value-of select='(ancestor-or-self::*[@stability])[last()]/@stability'/></td>
	         <td>
	          <xsl:variable name='arch' select='(ancestor-or-self::*[@arch])[last()]/@arch'/>
	          <xsl:choose>
	            <xsl:when test='$arch = "*-src"'>Source code</xsl:when>
	            <xsl:when test='not($arch)'>Any</xsl:when>
	            <xsl:otherwise><xsl:value-of select='$arch'/></xsl:otherwise>
	          </xsl:choose>
	         </td>
	         <td>
	          <xsl:for-each select='.//zi:archive'>
	           <a href='{@href}'>Download</a> (<xsl:value-of select='@size'/> bytes)
	          </xsl:for-each>
	         </td>
	        </tr>
	       </xsl:for-each>
	      </table>
	    </xsl:when>
	    <xsl:otherwise>
	      <p>No versions are available for downlad.</p>
	    </xsl:otherwise>
	  </xsl:choose>
	</dd>

	<dt>Required libraries</dt>
	<dd>
	 <xsl:choose>
	   <xsl:when test='//zi:requires'>
	     <p>The list below is just for information; Zero Install will automatically download any required
	     libraries for you.
	     </p>
	      <ul>
	       <xsl:for-each select='//zi:requires'>
	         <xsl:variable name='interface' select='@interface'/>
		 <xsl:if test='not(preceding::zi:requires[@interface = $interface])'>
	           <li><a><xsl:attribute name='href'><xsl:value-of select='$interface'/></xsl:attribute><xsl:value-of select='$interface'/></a></li>
		 </xsl:if>
	       </xsl:for-each>
	      </ul>
	    </xsl:when>
	    <xsl:otherwise>
	      <p>This feed does not list any additional requirements.</p>
	    </xsl:otherwise>
	  </xsl:choose>
	</dd>
	</dl>
       </div>
      </body>
    </html>
  </xsl:template>
  
  <xsl:template mode='dl' match='/zi:interface/@uri'>
    <dt>Full name</dt><dd><p><a href='{.}'><xsl:value-of select="."/></a></p></dd>
  </xsl:template>

  <xsl:template mode='dl' match='zi:homepage'>
    <dt>Homepage</dt><dd><p><a href='{.}'><xsl:value-of select="."/></a></p></dd>
  </xsl:template>

  <xsl:template mode='dl' match='zi:description'>
    <dt>Description</dt><dd><p><xsl:value-of select="."/></p></dd>
  </xsl:template>

  <xsl:template mode='dl' match='zi:icon'>
    <dt>Icon</dt><dd><p><img src='{@href}'/></p></dd>
  </xsl:template>

  <xsl:template mode='dl' match='*|@*'/>

  <xsl:template match='zi:group'>
    <dl class='group'>
      <xsl:apply-templates mode='attribs' select='@stability|@version|@id|@arch|@released'/>
      <xsl:apply-templates select='zi:group|zi:requires|zi:implementation'/>
    </dl>
  </xsl:template>

  <xsl:template match='zi:requires'>
    <dt>Requires</dt>
    <dd><a href='{@interface}'><xsl:value-of select='@interface'/></a></dd>
  </xsl:template>

  <xsl:template match='zi:implementation'>
    <dl class='impl'>
      <xsl:apply-templates mode='attribs' select='@stability|@version|@id|@arch|@released'/>
      <xsl:apply-templates/>
    </dl>
  </xsl:template>

  <xsl:template mode='attribs' match='@*'>
    <dt><xsl:value-of select='name(.)'/></dt>
    <dd><xsl:value-of select='.'/></dd>
  </xsl:template>

  <xsl:template match='zi:archive'>
    <dt>Download</dt>
    <dd><a href='{@href}'><xsl:value-of select='@href'/></a>
    (<xsl:value-of select='@size'/> bytes)</dd>
  </xsl:template>

</xsl:stylesheet>
