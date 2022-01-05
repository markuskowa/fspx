pes = dlmread('inputs/pes.dat', '', 3, 0);
xe = linspace(45, 90, 100);
fe = interp1(pes(:,1), pes(:,2), xe, 'pchip');

fe = fe - min(fe);
dlmwrite('pes_interp.dat', [xe' fe'], ' ');

