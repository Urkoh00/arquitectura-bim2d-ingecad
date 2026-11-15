# SPDX-License-Identifier: GPL-3.0-or-later
"""Evidence for straight openings. Does not infer height from a 2D stroke.

The existing reader still owns face pairing and wall topology. This adapter
refines its gaps against both drawn faces and keeps leaf evidence through
preview/commit instead of encoding it in a door's width.
"""
from __future__ import annotations
import math
from .vendor import walldetect as W

TOL = .005


def key(mid, width):
    return tuple(round(float(v), 6) for v in (*mid, width))


class Reader:
    def __init__(self, faces, context, entities):
        self.faces = faces
        self.context = context
        self.arcs = []
        self.lines = []
        self.details = {}
        self.warnings = set()
        self.claimed_arcs={}
        self.claimed_lines={}
        from .convert_tools import _pieces
        for entity, role in entities:
            if role not in ('carpinteria','puertas','ventanas','vanos'):continue
            segs, arcs = _pieces(entity)
            self.arcs.extend((c, r, a, b, role) for c, r, a, b in arcs)
            self.lines.extend((s, role) for s in segs)

    def adjust(self, mid, width, u, t):
        """The common *absence* of both faces, not the absence of their
        common overlap. Never enlarge the inferred hole or move the wall axis.
        Keep an unsupported gap unchanged for the existing manual review.
        """
        def unsupported():
            self.warnings.add('Jambas sin apoyo inequívoco en ambas caras: anchura previa conservada; revise el hueco antes de confirmar')
            return mid,width
        n = W._perp(u)
        bounds = []
        for face in (-t/2, t/2):
            intervals = []
            for s in self.faces:
                a, b = s[:2], s[2:4]
                d = W._sub(b, a)
                if W._len(d) < 1e-8 or abs(W._dot(W._unit_v(d), u)) < math.cos(math.radians(W.ANG_TOL)):
                    continue
                if max(abs(W._dot(W._sub(p, mid), n)-face) for p in (a,b)) > TOL + 1e-8:
                    continue
                intervals.append(sorted(W._dot(W._sub(p,mid),u) for p in (a,b)))
            # A solid face through the centre is not evidence for a jamb.
            if any(a < -TOL and b > TOL for a,b in intervals):
                return unsupported()
            left = [b for a,b in intervals if b <= TOL]
            right = [a for a,b in intervals if a >= -TOL]
            if not left or not right:
                return unsupported()
            bounds.append((max(left),min(right)))
        lo=max(b[0] for b in bounds); hi=min(b[1] for b in bounds)
        if not W.OPEN_MIN <= hi-lo <= width+TOL:
            return unsupported()
        if lo < -width/2-TOL or hi > width/2+TOL:
            return unsupported()
        return W._add(mid,W._mul(u,(lo+hi)/2)), hi-lo

    def swings(self, mid, width, u, t):
        n=W._perp(u); hits=[[],[]]
        margin=max(.06,min(.20,.13*width))
        for c,r,a,b,role in self.arcs:
            if not math.radians(40) <= b-a <= math.radians(130):
                continue
            along=W._dot(W._sub(c,mid),u); across=W._dot(W._sub(c,mid),n)
            end=0 if along<0 else 1
            if abs(along-(-width/2 if end==0 else width/2))>margin or abs(across)>t/2+.04:
                continue
            if not .30<=r<=width+margin:
                continue
            vectors=[(math.cos(x),math.sin(x)) for x in (a,b)]
            inward=1 if end==0 else -1
            # One end of the swing points into the actual gap, not into the
            # neighbouring room. Its other end lies outside the wall band.
            if max(inward*W._dot(v,u) for v in vectors)<.94:
                continue
            normal=W._dot((math.cos((a+b)/2),math.sin((a+b)/2)),n)
            side=1 if normal>=0 else -1
            if abs(normal)<.25:
                continue
            hit=(r,side,abs(abs(along)-width/2),c,a,b)
            if not any(math.dist(c,h[3])<TOL and abs(r-h[0])<TOL for h in hits[end]):
                hits[end].append(hit)
        pairs=[(a,b) for a in hits[0] for b in hits[1]
               if a[1]==b[1] and abs(a[0]+b[0]-width)<=max(.08,.18*width)]
        if pairs:
            a,b=min(pairs,key=lambda pair:abs(pair[0][0]+pair[1][0]-width)+pair[0][2]+pair[1][2])
            self.claimed_arcs[key(mid,width)]={self.arc_token(h[3],h[0],h[4],h[5])for h in (a,b)}
            clear=max(.01,width-.06)
            return ('door',-1,a[1]), {'operation':'SWINGING','leaves':2,
                'leaf':clear*a[0]/(a[0]+b[0]),'leaf2':clear*b[0]/(a[0]+b[0])}
        single=[(end,h) for end,group in enumerate(hits) for h in group
                if abs(h[0]-width)<=max(.08,.20*width)]
        if single:
            end,h=min(single,key=lambda p:abs(p[1][0]-width)+p[1][2])
            self.claimed_arcs[key(mid,width)]={self.arc_token(h[3],h[0],h[4],h[5])}
            return ('door',-1 if end==0 else 1,h[1]),{'operation':'SWINGING','leaves':1}
        return None

    @staticmethod
    def arc_token(c,r,a,b):return tuple(round(float(v),6)for v in (*c,r,a,b))

    @staticmethod
    def line_token(s):return tuple(round(float(v),6)for p in sorted((tuple(s[:2]),tuple(s[2:4])))for v in p)

    def owns(self,entity,mid,width,u,t,kind,attrs):
        """Hide only complete glyphs actually represented by this opening.
        Unknown furniture/curves must survive a conversion elsewhere.
        """
        from .convert_tools import _pieces
        lines,arcs=_pieces(entity)
        if not lines and not arcs:return False
        if kind=='void':return False
        if kind=='window' and attrs.get('face')!='distancia':return False
        claimed=self.claimed_arcs.get(key(mid,width),set())
        if any(kind!='door' or self.arc_token(*arc)not in claimed for arc in arcs):return False
        n=W._perp(u);margin=max(.08,min(.2,.15*width))
        for s in lines:
            if self.line_token(s)in self.claimed_lines.get(key(mid,width),set()):continue
            pts=[(W._dot(W._sub(p,mid),u),W._dot(W._sub(p,mid),n))for p in (s[:2],s[2:])]
            if min(x for x,y in pts)<-width/2-margin or max(x for x,y in pts)>width/2+margin:return False
            if max(abs(y)for x,y in pts)<=t/2+.20:continue
            # Open leaf: one end at a jamb, one end on the recognised swing.
            if kind!='door' or not any(
                math.dist(p,(cx,cy))<.10 and abs(math.dist(q,(cx,cy))-r)<.10
                for cx,cy,r,aa,bb in claimed for p,q in ((s[:2],s[2:]),(s[2:],s[:2]))):return False
        return True

    def sliding(self, mid, width, u, t):
        """Two offset, overlapping closed thin panels. A drawing of a
        sliding window can be identical: require an explicit door role.
        No threshold on width can establish its height above the floor.
        """
        n=W._perp(u);longs=[];caps=[]
        for s,role in self.lines:
            points=[(W._dot(W._sub(p,mid),u),W._dot(W._sub(p,mid),n)) for p in (s[:2],s[2:4])]
            (a,y),(b,z)=points
            if max(abs(y),abs(z))>t/2+.35 or min(a,b)<-2*width or max(a,b)>2*width:
                continue
            if abs(y-z)<=TOL and .3*width<=abs(b-a)<=1.10*width:
                longs.append((min(a,b),max(a,b),(y+z)/2,role))
            if abs(a-b)<=TOL and .008<=abs(z-y)<=.08:
                caps.append(((a+b)/2,min(y,z),max(y,z)))
        panels=[]
        for i,(a,b,y,role) in enumerate(longs):
            for c,d,z,role2 in longs[i+1:]:
                if max(abs(a-c),abs(b-d))>TOL or not .008<=abs(y-z)<=.08:
                    continue
                if all(any(abs(x-cap[0])<=TOL and abs(min(y,z)-cap[1])<=TOL
                           and abs(max(y,z)-cap[2])<=TOL for cap in caps) for x in (a,b)):
                    panels.append((a,b,(y+z)/2,role=='puertas' or role2=='puertas',role=='ventanas' or role2=='ventanas',min(y,z),max(y,z)))
        # Two parked leaves on opposite jambs, outside the wall band.
        # The same plan may be a window: an explicit door category is needed.
        for i,p in enumerate(panels):
            for q in panels[i+1:]:
                left,right=sorted((p,q))
                if not (abs(left[1]+width/2)<=.10 and abs(right[0]-width/2)<=.10
                        and .35*width<=left[1]-left[0]<=.65*width
                        and .35*width<=right[1]-right[0]<=.65*width
                        and left[2]*right[2]>0 and abs(left[2]-right[2])<=.08
                        and min(abs(left[2]),abs(right[2]))>t/2+.005):continue
                tokens=set()
                for s,role in self.lines:
                    pts=[(W._dot(W._sub(x,mid),u),W._dot(W._sub(x,mid),n))for x in (s[:2],s[2:4])]
                    if any(all(a-TOL<=x<=b+TOL and lo-TOL<=y<=hi+TOL for x,y in pts)
                           for a,b,yy,door,win,lo,hi in (left,right)):
                        tokens.add(self.line_token(s))
                self.claimed_lines[key(mid,width)]=tokens
                if p[4]or q[4]:return ('window',0,0),{}
                if p[3]or q[3]:
                    return ('door',-1,1 if p[2]>0 else -1),{'operation':'SLIDING','leaves':2,'face':'interior','frame_depth':min(.05,t)}
                self.warnings.add('Corredera exterior ambigua: designe Puertas o Ventanas; se conserva el dibujo')
                return ('void',0,0),{}
        for i,p in enumerate(panels):
            for q in panels[i+1:]:
                left,right=sorted((p,q))
                if not (.01<=left[1]-right[0]<=.20*width and abs(left[2]-right[2])>=.008):
                    continue
                if abs(left[0]+width/2)>.08 or abs(right[1]-width/2)>.08:
                    continue
                side=1 if p[2]+q[2]>=0 else -1
                if p[4] or q[4]:
                    return ('window',0,0),{}
                if p[3] or q[3]:
                    return ('door',-1,side),{'operation':'SLIDING','leaves':2}
                self.warnings.add('Paneles correderos ambiguos: puerta o ventana; designe como Puertas o Ventanas antes de confirmar')
                return ('void',0,0),{}
        for panel in panels:
            a,b,y,door,window=panel[:5]
            pocket=((abs(a-width/2)<=.08 and b>width/2) or
                    (abs(b+width/2)<=.08 and a<-width/2))
            if pocket and .7*width<=b-a<=1.1*width and abs(y)<t/2:
                if window:return ('window',0,0),{}
                if door:
                    return ('door',1 if a>0 else -1,1 if y>=0 else -1),{'operation':'SLIDING','leaves':1}
                self.warnings.add('Panel junto a jamba compatible con bolsillo, sin altura demostrada: designe la categoría; se conserva como vano ambiguo')
                return ('void',0,0),{}
        return None

    def read(self, mid, width, u, t):
        # Exact arcs have priority over a nearby flattened stroke. Leaf count
        # is semantic data independent of overall frame width.
        evidence=self.swings(mid,width,u,t) or self.sliding(mid,width,u,t)
        if evidence:
            result,attrs=evidence;self.details[key(mid,width)]=attrs
            return result
        return W._gap_kind(mid,width,u,t,self.context)

    def attributes(self, walls, ops):
        attrs=[]
        for k,pos,width,kind,_hinge,_side in ops:
            a,b,_t=walls[k];u=W._unit_v(W._sub(b,a));mid=W._add(a,W._mul(u,pos))
            attrs.append(dict(self.details.get(key(mid,width),{})) if kind=='door' else {})
        return attrs
