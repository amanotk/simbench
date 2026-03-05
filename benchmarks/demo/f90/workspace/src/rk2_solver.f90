module rk2_solver
   implicit none
contains

   subroutine solve_rk2_midpoint(rhs, y0, t0, h, n_steps, y_out)
      implicit none
      interface
         function rhs(t, y)
            real(8) :: rhs
            real(8), intent(in) :: t, y
         end function rhs
      end interface
      real(8), intent(in) :: y0, t0, h
      integer, intent(in) :: n_steps
      real(8), intent(out) :: y_out(0:n_steps)
      integer :: i

      y_out(0) = y0
      do i = 1, n_steps
         y_out(i) = 0.0d0
      end do
   end subroutine solve_rk2_midpoint

   real(8) function exp_growth_rhs(t, y)
      implicit none
      real(8), intent(in) :: t, y
      exp_growth_rhs = y
   end function exp_growth_rhs

   real(8) function damped_forced_rhs(t, y)
      implicit none
      real(8), intent(in) :: t, y
      damped_forced_rhs = -2.0d0*y + t
   end function damped_forced_rhs

end module rk2_solver
